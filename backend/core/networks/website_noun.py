"""Website-Noun bipartite network builder for Phase 6.

Builds networks connecting websites to extracted nouns based on TF-IDF scores.
"""
from typing import List, Dict, Any, Optional
import logging
import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from collections import defaultdict

from backend.core.networks.base import NetworkBuilder
from backend.models.website import WebsiteContent
from backend.models.analysis import ExtractedNoun
from backend.models.scraping import ScrapingJob

logger = logging.getLogger(__name__)


class WebsiteNounNetworkBuilder(NetworkBuilder):
    """
    Build bipartite network: websites → nouns.

    Network structure:
    - Website nodes: represent websites/URLs
    - Noun nodes: represent extracted nouns (lemmatized)
    - Edges: weighted by TF-IDF scores
    """

    def __init__(
        self,
        name: str,
        session: AsyncSession,
        session_ids: List[int],
        top_n_nouns: int = 50,
        languages: Optional[List[str]] = None,
        min_tfidf_score: float = 0.0,
        aggregate_by_domain: bool = True,
    ):
        """
        Initialize the website-noun network builder.

        Args:
            name: Network name
            session: Database session
            session_ids: List of search session IDs
            top_n_nouns: Top N nouns per website to include
            languages: List of languages to include (None = all)
            min_tfidf_score: Minimum TF-IDF score to include
            aggregate_by_domain: If True, aggregate URLs by domain
        """
        super().__init__(name, "website_noun")
        self.session = session
        self.session_ids = session_ids
        self.top_n_nouns = top_n_nouns
        self.languages = languages
        self.min_tfidf_score = min_tfidf_score
        self.aggregate_by_domain = aggregate_by_domain

        # Add metadata
        self.add_metadata("session_ids", session_ids)
        self.add_metadata("top_n_nouns", top_n_nouns)
        self.add_metadata("languages", languages)
        self.add_metadata("min_tfidf_score", min_tfidf_score)
        self.add_metadata("aggregate_by_domain", aggregate_by_domain)

    async def build(self) -> nx.Graph:
        """
        Build the website-noun bipartite network.

        Returns:
            NetworkX Graph object
        """
        logger.info(
            f"Building website-noun network for sessions: {self.session_ids}"
        )

        # Create undirected graph (bipartite)
        self.create_graph(directed=False)

        # Load website contents from scraping jobs linked to sessions
        contents = await self._load_website_contents()
        logger.info(f"Loaded {len(contents)} website contents")

        if not contents:
            logger.warning("No website contents found for the specified sessions")
            return self.graph

        # Build nodes and edges
        website_count = 0
        noun_count = 0
        edge_count = 0

        # Track websites and nouns to avoid duplicates
        websites_seen = set()
        nouns_seen = set()

        # If aggregating by domain, collect nouns per domain
        if self.aggregate_by_domain:
            domain_nouns = await self._aggregate_nouns_by_domain(contents)

            for domain, nouns_data in domain_nouns.items():
                # Add website node
                website_node_id = self._sanitize_node_id(f"website_{domain}")

                if website_node_id not in websites_seen:
                    self.add_node(
                        website_node_id,
                        node_type="website",
                        label=domain,
                        domain=domain,
                    )
                    websites_seen.add(website_node_id)
                    website_count += 1

                # Add top N nouns for this domain
                for noun_data in nouns_data[: self.top_n_nouns]:
                    lemma = noun_data["lemma"]
                    tfidf_score = noun_data["avg_tfidf_score"]

                    if tfidf_score < self.min_tfidf_score:
                        continue

                    # Add noun node
                    noun_node_id = self._sanitize_node_id(f"noun_{lemma}")

                    if noun_node_id not in nouns_seen:
                        self.add_node(
                            noun_node_id,
                            node_type="noun",
                            label=lemma,
                            lemma=lemma,
                            language=noun_data["language"],
                        )
                        nouns_seen.add(noun_node_id)
                        noun_count += 1

                    # Add edge with TF-IDF as weight
                    self.add_edge(
                        website_node_id,
                        noun_node_id,
                        weight=tfidf_score,
                        frequency=noun_data["total_frequency"],
                    )
                    edge_count += 1

        else:
            # Process each website content individually
            for content in contents:
                # Load nouns for this content
                nouns = await self._load_nouns_for_content(content.id)

                if not nouns:
                    continue

                # Add website node
                website_node_id = self._sanitize_node_id(f"website_{content.url}")

                if website_node_id not in websites_seen:
                    # Extract domain from URL
                    from urllib.parse import urlparse
                    parsed = urlparse(content.url)
                    domain = parsed.netloc or parsed.path.split('/')[0]

                    self.add_node(
                        website_node_id,
                        node_type="website",
                        label=content.url,
                        url=content.url,
                        domain=domain,
                        title=content.title,
                    )
                    websites_seen.add(website_node_id)
                    website_count += 1

                # Add top N nouns
                for noun in nouns[: self.top_n_nouns]:
                    if noun.tfidf_score < self.min_tfidf_score:
                        continue

                    # Add noun node
                    noun_node_id = self._sanitize_node_id(f"noun_{noun.lemma}")

                    if noun_node_id not in nouns_seen:
                        self.add_node(
                            noun_node_id,
                            node_type="noun",
                            label=noun.lemma,
                            lemma=noun.lemma,
                            language=noun.language,
                        )
                        nouns_seen.add(noun_node_id)
                        noun_count += 1

                    # Add edge
                    self.add_edge(
                        website_node_id,
                        noun_node_id,
                        weight=noun.tfidf_score,
                        frequency=noun.frequency,
                    )
                    edge_count += 1

        # Update metadata
        self.add_metadata("website_count", website_count)
        self.add_metadata("noun_count", noun_count)
        self.add_metadata("edge_count", edge_count)

        # Validate bipartite structure
        is_valid = self.validate_bipartite(("website", "noun"))
        if not is_valid:
            logger.error("Graph failed bipartite validation")

        logger.info(
            f"Built website-noun network: {website_count} websites, "
            f"{noun_count} nouns, {edge_count} edges"
        )

        return self.graph

    async def _load_website_contents(self) -> List[WebsiteContent]:
        """
        Load website contents from scraping jobs linked to sessions.

        Returns:
            List of WebsiteContent objects
        """
        # First get scraping job IDs from the sessions
        stmt_jobs = (
            select(ScrapingJob.id)
            .where(ScrapingJob.session_id.in_(self.session_ids))
            .where(ScrapingJob.status == "completed")
        )

        result_jobs = await self.session.execute(stmt_jobs)
        job_ids = [row[0] for row in result_jobs.all()]

        if not job_ids:
            return []

        # Load website contents
        stmt = (
            select(WebsiteContent)
            .where(WebsiteContent.scraping_job_id.in_(job_ids))
            .where(WebsiteContent.status == "success")
        )

        # Filter by language if specified
        if self.languages:
            stmt = stmt.where(WebsiteContent.language.in_(self.languages))

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _load_nouns_for_content(
        self, content_id: int
    ) -> List[ExtractedNoun]:
        """
        Load nouns for a website content, ordered by TF-IDF score.

        Args:
            content_id: Website content ID

        Returns:
            List of ExtractedNoun objects
        """
        stmt = (
            select(ExtractedNoun)
            .where(ExtractedNoun.website_content_id == content_id)
            .order_by(ExtractedNoun.tfidf_score.desc())
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _aggregate_nouns_by_domain(
        self, contents: List[WebsiteContent]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Aggregate nouns by domain.

        Args:
            contents: List of WebsiteContent objects

        Returns:
            Dictionary mapping domain to list of aggregated noun data
        """
        from urllib.parse import urlparse

        # Group contents by domain
        domain_content_ids = defaultdict(list)
        for content in contents:
            # Extract domain from URL
            parsed = urlparse(content.url)
            domain = parsed.netloc or parsed.path.split('/')[0]
            domain_content_ids[domain].append(content.id)

        # Load and aggregate nouns for each domain
        domain_nouns = {}

        for domain, content_ids in domain_content_ids.items():
            # Load all nouns for this domain's contents
            stmt = (
                select(ExtractedNoun)
                .where(ExtractedNoun.website_content_id.in_(content_ids))
            )

            result = await self.session.execute(stmt)
            nouns = list(result.scalars().all())

            # Aggregate by lemma
            lemma_stats = defaultdict(
                lambda: {
                    "total_frequency": 0,
                    "total_tfidf": 0.0,
                    "count": 0,
                    "language": None,
                }
            )

            for noun in nouns:
                stats = lemma_stats[noun.lemma]
                stats["total_frequency"] += noun.frequency
                stats["total_tfidf"] += noun.tfidf_score
                stats["count"] += 1
                if stats["language"] is None:
                    stats["language"] = noun.language

            # Convert to list and calculate averages
            aggregated = []
            for lemma, stats in lemma_stats.items():
                aggregated.append(
                    {
                        "lemma": lemma,
                        "total_frequency": stats["total_frequency"],
                        "avg_tfidf_score": stats["total_tfidf"] / stats["count"],
                        "content_count": stats["count"],
                        "language": stats["language"],
                    }
                )

            # Sort by average TF-IDF
            aggregated.sort(key=lambda x: x["avg_tfidf_score"], reverse=True)

            domain_nouns[domain] = aggregated

        return domain_nouns

    async def get_top_nouns(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get top N nouns by degree (number of websites they appear in).

        Args:
            top_n: Number of top nouns to return

        Returns:
            List of noun dictionaries
        """
        if self.graph is None:
            return []

        nouns = []
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") == "noun":
                degree = self.graph.degree(node)

                # Calculate average weight
                edges = self.graph.edges(node, data=True)
                weights = [d.get("weight", 1.0) for _, _, d in edges]
                avg_weight = sum(weights) / len(weights) if weights else 0

                nouns.append(
                    {
                        "lemma": data.get("lemma"),
                        "language": data.get("language"),
                        "degree": degree,
                        "avg_tfidf": avg_weight,
                    }
                )

        # Sort by degree
        nouns.sort(key=lambda x: x["degree"], reverse=True)

        return nouns[:top_n]

    async def get_top_websites(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get top N websites by degree (number of nouns).

        Args:
            top_n: Number of top websites to return

        Returns:
            List of website dictionaries
        """
        if self.graph is None:
            return []

        websites = []
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") == "website":
                degree = self.graph.degree(node)
                websites.append(
                    {
                        "node_id": node,
                        "domain": data.get("domain"),
                        "url": data.get("url"),
                        "degree": degree,
                    }
                )

        # Sort by degree
        websites.sort(key=lambda x: x["degree"], reverse=True)

        return websites[:top_n]
