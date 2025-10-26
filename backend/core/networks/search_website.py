"""Search-Website bipartite network builder for Phase 6.

Builds networks connecting search queries to websites based on search result rankings.
Follows Richard Rogers' issue mapping methodology.
"""
from typing import List, Dict, Any, Optional
import logging
import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from urllib.parse import urlparse

from backend.core.networks.base import NetworkBuilder
from backend.models.search import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class SearchWebsiteNetworkBuilder(NetworkBuilder):
    """
    Build bipartite network: search queries → websites.

    Network structure:
    - Query nodes: represent search queries
    - Website nodes: represent websites/URLs
    - Edges: weighted by search result ranking (rank 1 = highest weight)
    """

    def __init__(
        self,
        name: str,
        session: AsyncSession,
        session_ids: List[int],
        weight_method: str = "inverse_rank",
        aggregate_by_domain: bool = True,
    ):
        """
        Initialize the search-website network builder.

        Args:
            name: Network name
            session: Database session
            session_ids: List of search session IDs to include
            weight_method: Method for calculating edge weights from rank
                          Options: inverse_rank, exponential_decay, fixed
            aggregate_by_domain: If True, aggregate URLs by domain
        """
        super().__init__(name, "search_website")
        self.session = session
        self.session_ids = session_ids
        self.weight_method = weight_method
        self.aggregate_by_domain = aggregate_by_domain

        # Add metadata
        self.add_metadata("session_ids", session_ids)
        self.add_metadata("weight_method", weight_method)
        self.add_metadata("aggregate_by_domain", aggregate_by_domain)

    async def build(self) -> nx.Graph:
        """
        Build the search-website bipartite network.

        Returns:
            NetworkX Graph object

        Process:
        1. Load all search queries from specified sessions
        2. Load all search results
        3. Create query nodes
        4. Create website nodes
        5. Create edges with weights based on ranking
        """
        logger.info(
            f"Building search-website network for sessions: {self.session_ids}"
        )

        # Create undirected graph (bipartite)
        self.create_graph(directed=False)

        # Load queries and results
        queries = await self._load_queries()
        logger.info(f"Loaded {len(queries)} search queries")

        if not queries:
            logger.warning("No queries found for the specified sessions")
            return self.graph

        # Build nodes and edges
        query_count = 0
        website_count = 0
        edge_count = 0

        # Track websites to avoid duplicates
        websites_seen = set()

        for query in queries:
            # Add query node
            query_node_id = f"query_{query.id}"
            self.add_node(
                query_node_id,
                node_type="query",
                label=query.query_text,
                query_id=query.id,
                query_text=query.query_text,
                search_engine=query.search_engine,
                session_id=query.session_id,
            )
            query_count += 1

            # Load results for this query
            results = await self._load_results_for_query(query.id)

            for result in results:
                # Determine website identifier
                if self.aggregate_by_domain:
                    website_id = result.domain
                    website_label = result.domain
                else:
                    website_id = result.url
                    website_label = result.url

                website_node_id = self._sanitize_node_id(f"website_{website_id}")

                # Add website node if not already added
                if website_node_id not in websites_seen:
                    self.add_node(
                        website_node_id,
                        node_type="website",
                        label=website_label,
                        url=result.url if not self.aggregate_by_domain else None,
                        domain=result.domain,
                        title=result.title,
                    )
                    websites_seen.add(website_node_id)
                    website_count += 1

                # Calculate edge weight from rank
                weight = self._calculate_weight_from_rank(result.rank)

                # Add edge
                self.add_edge(
                    query_node_id,
                    website_node_id,
                    weight=weight,
                    rank=result.rank,
                    search_result_id=result.id,
                )
                edge_count += 1

        # Update metadata
        self.add_metadata("query_count", query_count)
        self.add_metadata("website_count", website_count)
        self.add_metadata("edge_count", edge_count)

        # Validate bipartite structure
        is_valid = self.validate_bipartite(("query", "website"))
        if not is_valid:
            logger.error("Graph failed bipartite validation")

        logger.info(
            f"Built search-website network: {query_count} queries, "
            f"{website_count} websites, {edge_count} edges"
        )

        return self.graph

    async def _load_queries(self) -> List[SearchQuery]:
        """
        Load all search queries from specified sessions.

        Returns:
            List of SearchQuery objects
        """
        stmt = (
            select(SearchQuery)
            .where(SearchQuery.session_id.in_(self.session_ids))
            .where(SearchQuery.status == "completed")
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _load_results_for_query(self, query_id: int) -> List[SearchResult]:
        """
        Load all search results for a query.

        Args:
            query_id: Search query ID

        Returns:
            List of SearchResult objects
        """
        stmt = (
            select(SearchResult)
            .where(SearchResult.query_id == query_id)
            .order_by(SearchResult.rank)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _calculate_weight_from_rank(self, rank: int) -> float:
        """
        Calculate edge weight from search result rank.

        Args:
            rank: Search result rank (1-based)

        Returns:
            Edge weight

        Methods:
        - inverse_rank: 1/rank (rank 1 = weight 1.0, rank 10 = weight 0.1)
        - exponential_decay: exp(-rank/10) (smoother decay)
        - fixed: All edges have weight 1.0
        """
        if self.weight_method == "inverse_rank":
            return 1.0 / rank

        elif self.weight_method == "exponential_decay":
            import math
            return math.exp(-rank / 10.0)

        elif self.weight_method == "fixed":
            return 1.0

        else:
            logger.warning(
                f"Unknown weight method '{self.weight_method}', using inverse_rank"
            )
            return 1.0 / rank

    async def get_top_websites(
        self,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get top N websites by degree (number of queries they appear in).

        Args:
            top_n: Number of top websites to return

        Returns:
            List of website dictionaries
        """
        if self.graph is None:
            return []

        # Get websites and their degrees
        websites = []
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") == "website":
                degree = self.graph.degree(node)
                websites.append(
                    {
                        "node_id": node,
                        "domain": data.get("domain"),
                        "url": data.get("url"),
                        "title": data.get("title"),
                        "degree": degree,
                        "label": data.get("label"),
                    }
                )

        # Sort by degree
        websites.sort(key=lambda x: x["degree"], reverse=True)

        return websites[:top_n]

    async def get_top_queries(
        self,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get top N queries by degree (number of websites they returned).

        Args:
            top_n: Number of top queries to return

        Returns:
            List of query dictionaries
        """
        if self.graph is None:
            return []

        # Get queries and their degrees
        queries = []
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") == "query":
                degree = self.graph.degree(node)
                queries.append(
                    {
                        "node_id": node,
                        "query_text": data.get("query_text"),
                        "search_engine": data.get("search_engine"),
                        "degree": degree,
                    }
                )

        # Sort by degree
        queries.sort(key=lambda x: x["degree"], reverse=True)

        return queries[:top_n]

    async def get_query_overlap_matrix(self) -> Dict[str, Any]:
        """
        Calculate overlap between queries (shared websites).

        Returns:
            Dictionary with overlap statistics
        """
        if self.graph is None:
            return {}

        # Get all query nodes
        query_nodes = [
            node
            for node, data in self.graph.nodes(data=True)
            if data.get("node_type") == "query"
        ]

        # Calculate pairwise overlaps
        overlaps = []
        for i, q1 in enumerate(query_nodes):
            q1_websites = set(self.graph.neighbors(q1))

            for q2 in query_nodes[i + 1 :]:
                q2_websites = set(self.graph.neighbors(q2))

                # Calculate Jaccard similarity
                intersection = len(q1_websites & q2_websites)
                union = len(q1_websites | q2_websites)

                if union > 0:
                    jaccard = intersection / union
                    overlaps.append(
                        {
                            "query1": self.graph.nodes[q1].get("query_text"),
                            "query2": self.graph.nodes[q2].get("query_text"),
                            "shared_websites": intersection,
                            "jaccard_similarity": jaccard,
                        }
                    )

        # Sort by shared websites
        overlaps.sort(key=lambda x: x["shared_websites"], reverse=True)

        return {
            "total_comparisons": len(overlaps),
            "top_overlaps": overlaps[:20],
            "avg_jaccard": (
                sum(o["jaccard_similarity"] for o in overlaps) / len(overlaps)
                if overlaps
                else 0
            ),
        }
