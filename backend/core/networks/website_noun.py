"""Website-Keyword (formerly Noun) bipartite network builder for Phase 6.

Enhanced in v6.0.0 to support multiple extraction methods:
- noun: Original spaCy noun extraction (backward compatible)
- all_pos: Extract nouns, verbs, adjectives
- tfidf: TF-IDF with optional bigrams
- rake: RAKE algorithm with n-grams

Builds networks connecting websites to extracted keywords based on TF-IDF scores.
"""
from typing import List, Dict, Any, Optional
import logging
import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from collections import defaultdict

from backend.core.networks.base import NetworkBuilder
from backend.models.website import WebsiteContent
from backend.models.analysis import ExtractedNoun, ExtractedKeyword
from backend.models.scraping import ScrapingJob
from backend.schemas.analysis import KeywordExtractionConfig

logger = logging.getLogger(__name__)


class WebsiteNounNetworkBuilder(NetworkBuilder):
    """
    Build bipartite network: websites → keywords (nouns).

    Enhanced in v6.0.0 to support multiple extraction methods.
    This class maintains backward compatibility while supporting new keyword types.

    Network structure:
    - Website nodes: represent websites/URLs
    - Keyword nodes: represent extracted keywords (lemmatized)
    - Edges: weighted by TF-IDF or importance scores

    Note: Class name kept as WebsiteNounNetworkBuilder for backward compatibility.
    Use WebsiteKeywordNetworkBuilder alias for clarity in new code.
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
        keyword_config: Optional[KeywordExtractionConfig] = None,
    ):
        """
        Initialize the website-keyword network builder.

        Args:
            name: Network name
            session: Database session
            session_ids: List of search session IDs
            top_n_nouns: Top N keywords per website to include (kept for backward compat)
            languages: List of languages to include (None = all)
            min_tfidf_score: Minimum TF-IDF score to include
            aggregate_by_domain: If True, aggregate URLs by domain
            keyword_config: Configuration for keyword extraction filtering (v6.0.0)
        """
        super().__init__(name, "website_keyword")
        self.session = session
        self.session_ids = session_ids
        self.top_n_nouns = top_n_nouns  # Kept for backward compatibility
        self.top_n_keywords = top_n_nouns  # Alias
        self.languages = languages
        self.min_tfidf_score = min_tfidf_score
        self.aggregate_by_domain = aggregate_by_domain

        # v6.0.0: Keyword extraction configuration
        self.keyword_config = keyword_config or KeywordExtractionConfig()

        # Add metadata
        self.add_metadata("session_ids", session_ids)
        self.add_metadata("top_n_keywords", top_n_nouns)
        self.add_metadata("languages", languages)
        self.add_metadata("min_tfidf_score", min_tfidf_score)
        self.add_metadata("aggregate_by_domain", aggregate_by_domain)
        self.add_metadata("keyword_method", self.keyword_config.method)
        self.add_metadata("extraction_config", self.keyword_config.model_dump())

    async def build(self) -> nx.Graph:
        """
        Build the website-keyword bipartite network.

        Enhanced in v6.0.0 to support filtering by extraction method.

        Returns:
            NetworkX Graph object
        """
        logger.info(
            f"Building website-keyword network for sessions: {self.session_ids}, "
            f"method: {self.keyword_config.method}"
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
        keyword_count = 0
        edge_count = 0

        # Track websites and keywords to avoid duplicates
        websites_seen = set()
        keywords_seen = set()

        # If aggregating by domain, collect keywords per domain
        if self.aggregate_by_domain:
            domain_keywords = await self._aggregate_keywords_by_domain(contents)

            for domain, keywords_data in domain_keywords.items():
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

                # Add top N keywords for this domain
                for keyword_data in keywords_data[: self.top_n_keywords]:
                    lemma = keyword_data["lemma"]
                    tfidf_score = keyword_data["avg_tfidf_score"]

                    if tfidf_score < self.min_tfidf_score:
                        continue

                    # Add keyword node
                    keyword_node_id = self._sanitize_node_id(f"keyword_{lemma}")

                    if keyword_node_id not in keywords_seen:
                        self.add_node(
                            keyword_node_id,
                            node_type="keyword",
                            label=lemma,
                            lemma=lemma,
                            language=keyword_data["language"],
                            extraction_method=keyword_data.get("extraction_method", "noun"),
                            phrase_length=keyword_data.get("phrase_length", 1),
                            pos_tag=keyword_data.get("pos_tag"),
                        )
                        keywords_seen.add(keyword_node_id)
                        keyword_count += 1

                    # Add edge with TF-IDF as weight
                    self.add_edge(
                        website_node_id,
                        keyword_node_id,
                        weight=tfidf_score,
                        frequency=keyword_data["total_frequency"],
                    )
                    edge_count += 1

        else:
            # Process each website content individually
            for content in contents:
                # Load keywords for this content
                keywords = await self._load_keywords_for_content(content.id)

                if not keywords:
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

                # Add top N keywords
                for keyword in keywords[: self.top_n_keywords]:
                    if keyword.tfidf_score < self.min_tfidf_score:
                        continue

                    # Add keyword node
                    keyword_node_id = self._sanitize_node_id(f"keyword_{keyword.lemma}")

                    if keyword_node_id not in keywords_seen:
                        self.add_node(
                            keyword_node_id,
                            node_type="keyword",
                            label=keyword.lemma,
                            lemma=keyword.lemma,
                            language=keyword.language,
                            extraction_method=keyword.extraction_method,
                            phrase_length=keyword.phrase_length or 1,
                            pos_tag=keyword.pos_tag,
                        )
                        keywords_seen.add(keyword_node_id)
                        keyword_count += 1

                    # Add edge
                    self.add_edge(
                        website_node_id,
                        keyword_node_id,
                        weight=keyword.tfidf_score,
                        frequency=keyword.frequency,
                    )
                    edge_count += 1

        # Update metadata
        self.add_metadata("website_count", website_count)
        self.add_metadata("keyword_count", keyword_count)
        self.add_metadata("edge_count", edge_count)

        # Validate bipartite structure
        is_valid = self.validate_bipartite(("website", "keyword"))
        if not is_valid:
            logger.error("Graph failed bipartite validation")

        logger.info(
            f"Built website-keyword network: {website_count} websites, "
            f"{keyword_count} keywords, {edge_count} edges"
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

    async def _load_keywords_for_content(
        self, content_id: int
    ) -> List[ExtractedKeyword]:
        """
        Load keywords for a website content, ordered by TF-IDF score.

        Enhanced in v6.0.0 to filter by extraction method.

        Args:
            content_id: Website content ID

        Returns:
            List of ExtractedKeyword objects
        """
        stmt = (
            select(ExtractedKeyword)
            .where(ExtractedKeyword.website_content_id == content_id)
            .where(ExtractedKeyword.extraction_method == self.keyword_config.method)
            .order_by(ExtractedKeyword.tfidf_score.desc())
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # Backward compatibility alias
    async def _load_nouns_for_content(
        self, content_id: int
    ) -> List[ExtractedNoun]:
        """Alias for backward compatibility."""
        return await self._load_keywords_for_content(content_id)

    async def _aggregate_keywords_by_domain(
        self, contents: List[WebsiteContent]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Aggregate keywords by domain.

        Enhanced in v6.0.0 to filter by extraction method and include metadata.

        Args:
            contents: List of WebsiteContent objects

        Returns:
            Dictionary mapping domain to list of aggregated keyword data
        """
        from urllib.parse import urlparse

        # Group contents by domain
        domain_content_ids = defaultdict(list)
        for content in contents:
            # Extract domain from URL
            parsed = urlparse(content.url)
            domain = parsed.netloc or parsed.path.split('/')[0]
            domain_content_ids[domain].append(content.id)

        # Load and aggregate keywords for each domain
        domain_keywords = {}

        for domain, content_ids in domain_content_ids.items():
            # Load all keywords for this domain's contents with filtering
            stmt = (
                select(ExtractedKeyword)
                .where(ExtractedKeyword.website_content_id.in_(content_ids))
                .where(ExtractedKeyword.extraction_method == self.keyword_config.method)
            )

            result = await self.session.execute(stmt)
            keywords = list(result.scalars().all())

            # Aggregate by lemma
            lemma_stats = defaultdict(
                lambda: {
                    "total_frequency": 0,
                    "total_tfidf": 0.0,
                    "count": 0,
                    "language": None,
                    "extraction_method": None,
                    "phrase_length": None,
                    "pos_tag": None,
                }
            )

            for keyword in keywords:
                stats = lemma_stats[keyword.lemma]
                stats["total_frequency"] += keyword.frequency
                stats["total_tfidf"] += keyword.tfidf_score
                stats["count"] += 1
                if stats["language"] is None:
                    stats["language"] = keyword.language
                if stats["extraction_method"] is None:
                    stats["extraction_method"] = keyword.extraction_method
                if stats["phrase_length"] is None:
                    stats["phrase_length"] = keyword.phrase_length
                if stats["pos_tag"] is None:
                    stats["pos_tag"] = keyword.pos_tag

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
                        "extraction_method": stats["extraction_method"],
                        "phrase_length": stats["phrase_length"],
                        "pos_tag": stats["pos_tag"],
                    }
                )

            # Sort by average TF-IDF
            aggregated.sort(key=lambda x: x["avg_tfidf_score"], reverse=True)

            domain_keywords[domain] = aggregated

        return domain_keywords

    # Backward compatibility alias
    async def _aggregate_nouns_by_domain(
        self, contents: List[WebsiteContent]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Alias for backward compatibility."""
        return await self._aggregate_keywords_by_domain(contents)

    async def get_top_keywords(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get top N keywords by degree (number of websites they appear in).

        Args:
            top_n: Number of top keywords to return

        Returns:
            List of keyword dictionaries
        """
        if self.graph is None:
            return []

        keywords = []
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") in ("keyword", "noun"):  # Support both types
                degree = self.graph.degree(node)

                # Calculate average weight
                edges = self.graph.edges(node, data=True)
                weights = [d.get("weight", 1.0) for _, _, d in edges]
                avg_weight = sum(weights) / len(weights) if weights else 0

                keywords.append(
                    {
                        "lemma": data.get("lemma"),
                        "language": data.get("language"),
                        "degree": degree,
                        "avg_tfidf": avg_weight,
                        "extraction_method": data.get("extraction_method"),
                        "phrase_length": data.get("phrase_length"),
                        "pos_tag": data.get("pos_tag"),
                    }
                )

        # Sort by degree
        keywords.sort(key=lambda x: x["degree"], reverse=True)

        return keywords[:top_n]

    # Backward compatibility alias
    async def get_top_nouns(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Alias for backward compatibility."""
        return await self.get_top_keywords(top_n)

    async def get_top_websites(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get top N websites by degree (number of keywords).

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


# Backward compatibility alias
WebsiteKeywordNetworkBuilder = WebsiteNounNetworkBuilder
