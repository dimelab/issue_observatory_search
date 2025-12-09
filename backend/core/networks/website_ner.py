"""Website-NER bipartite network builder for Phase 6 (v6.0.0).

New in v6.0.0: Build networks connecting websites to named entities (NER).

Based on implementation patterns from some2net (github.com/dimelab/some2net).
Adapted for Issue Observatory Search v6.0.0.

Supports:
- spaCy NER (fast, existing)
- Transformer-based NER (accurate, multilingual)
- Entity type filtering (PERSON, ORG, GPE, LOC, MISC)
- Confidence threshold filtering
"""
from typing import List, Dict, Any, Optional
import logging
import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from collections import defaultdict

from backend.core.networks.base import NetworkBuilder
from backend.models.website import WebsiteContent
from backend.models.analysis import ExtractedEntity
from backend.models.scraping import ScrapingJob
from backend.schemas.analysis import NERExtractionConfig

logger = logging.getLogger(__name__)


class WebsiteNERNetworkBuilder(NetworkBuilder):
    """
    Build bipartite network: websites → named entities.

    Network structure:
    - Website nodes: represent websites/URLs
    - Entity nodes: represent named entities (PERSON, ORG, GPE, LOC, etc.)
    - Edges: weighted by entity frequency or confidence scores

    Enhanced in v6.0.0 with:
    - Multi-lingual support (English, Danish)
    - Configurable entity type filtering
    - Confidence threshold filtering
    - Support for both spaCy and transformer-based NER
    """

    def __init__(
        self,
        name: str,
        session: AsyncSession,
        session_ids: List[int],
        top_n_entities: int = 50,
        languages: Optional[List[str]] = None,
        min_confidence: float = 0.85,
        aggregate_by_domain: bool = True,
        ner_config: Optional[NERExtractionConfig] = None,
    ):
        """
        Initialize the website-NER network builder.

        Args:
            name: Network name
            session: Database session
            session_ids: List of search session IDs
            top_n_entities: Top N entities per website to include
            languages: List of languages to include (None = all)
            min_confidence: Minimum confidence score to include
            aggregate_by_domain: If True, aggregate URLs by domain
            ner_config: Configuration for NER extraction filtering (v6.0.0)
        """
        super().__init__(name, "website_ner")
        self.session = session
        self.session_ids = session_ids
        self.top_n_entities = top_n_entities
        self.languages = languages
        self.min_confidence = min_confidence
        self.aggregate_by_domain = aggregate_by_domain

        # v6.0.0: NER extraction configuration
        self.ner_config = ner_config or NERExtractionConfig()

        # Add metadata
        self.add_metadata("session_ids", session_ids)
        self.add_metadata("top_n_entities", top_n_entities)
        self.add_metadata("languages", languages)
        self.add_metadata("min_confidence", min_confidence)
        self.add_metadata("aggregate_by_domain", aggregate_by_domain)
        self.add_metadata("ner_method", self.ner_config.extraction_method)
        self.add_metadata("entity_types", self.ner_config.entity_types)
        self.add_metadata("extraction_config", self.ner_config.model_dump())

    async def build(self) -> nx.Graph:
        """
        Build the website-NER bipartite network.

        Returns:
            NetworkX Graph object
        """
        logger.info(
            f"Building website-NER network for sessions: {self.session_ids}, "
            f"method: {self.ner_config.extraction_method}, "
            f"entity_types: {self.ner_config.entity_types}"
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
        entity_count = 0
        edge_count = 0

        # Track websites and entities to avoid duplicates
        websites_seen = set()
        entities_seen = set()

        # If aggregating by domain, collect entities per domain
        if self.aggregate_by_domain:
            domain_entities = await self._aggregate_entities_by_domain(contents)

            for domain, entities_data in domain_entities.items():
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

                # Add top N entities for this domain
                for entity_data in entities_data[: self.top_n_entities]:
                    entity_text = entity_data["text"]
                    entity_label = entity_data["label"]
                    confidence = entity_data["avg_confidence"]
                    frequency = entity_data["total_frequency"]

                    if confidence < self.min_confidence:
                        continue

                    # Add entity node (unique ID includes type)
                    entity_node_id = self._sanitize_node_id(
                        f"entity_{entity_label}_{entity_text}"
                    )

                    if entity_node_id not in entities_seen:
                        self.add_node(
                            entity_node_id,
                            node_type="entity",
                            label=entity_text,
                            entity_text=entity_text,
                            entity_label=entity_label,
                            language=entity_data["language"],
                            extraction_method=entity_data.get(
                                "extraction_method", "spacy"
                            ),
                        )
                        entities_seen.add(entity_node_id)
                        entity_count += 1

                    # Add edge with confidence * frequency as weight
                    edge_weight = confidence * frequency
                    self.add_edge(
                        website_node_id,
                        entity_node_id,
                        weight=edge_weight,
                        frequency=frequency,
                        confidence=confidence,
                    )
                    edge_count += 1

        else:
            # Process each website content individually
            for content in contents:
                # Load entities for this content
                entities = await self._load_entities_for_content(content.id)

                if not entities:
                    continue

                # Add website node
                website_node_id = self._sanitize_node_id(f"website_{content.url}")

                if website_node_id not in websites_seen:
                    # Extract domain from URL
                    from urllib.parse import urlparse

                    parsed = urlparse(content.url)
                    domain = parsed.netloc or parsed.path.split("/")[0]

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

                # Add top N entities
                for entity in entities[: self.top_n_entities]:
                    if entity.confidence < self.min_confidence:
                        continue

                    # Add entity node
                    entity_node_id = self._sanitize_node_id(
                        f"entity_{entity.label}_{entity.text}"
                    )

                    if entity_node_id not in entities_seen:
                        self.add_node(
                            entity_node_id,
                            node_type="entity",
                            label=entity.text,
                            entity_text=entity.text,
                            entity_label=entity.label,
                            language=entity.language,
                            extraction_method=entity.extraction_method,
                        )
                        entities_seen.add(entity_node_id)
                        entity_count += 1

                    # Add edge with confidence * frequency as weight
                    edge_weight = entity.confidence * entity.frequency
                    self.add_edge(
                        website_node_id,
                        entity_node_id,
                        weight=edge_weight,
                        frequency=entity.frequency,
                        confidence=entity.confidence,
                    )
                    edge_count += 1

        # Update metadata
        self.add_metadata("website_count", website_count)
        self.add_metadata("entity_count", entity_count)
        self.add_metadata("edge_count", edge_count)

        # Validate bipartite structure
        is_valid = self.validate_bipartite(("website", "entity"))
        if not is_valid:
            logger.error("Graph failed bipartite validation")

        logger.info(
            f"Built website-NER network: {website_count} websites, "
            f"{entity_count} entities, {edge_count} edges"
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

    async def _load_entities_for_content(
        self, content_id: int
    ) -> List[ExtractedEntity]:
        """
        Load entities for a website content, ordered by confidence * frequency.

        Enhanced in v6.0.0 to filter by extraction method and entity types.

        Args:
            content_id: Website content ID

        Returns:
            List of ExtractedEntity objects
        """
        stmt = (
            select(ExtractedEntity)
            .where(ExtractedEntity.website_content_id == content_id)
            .where(
                ExtractedEntity.extraction_method == self.ner_config.extraction_method
            )
            .where(ExtractedEntity.label.in_(self.ner_config.entity_types))
            .where(
                ExtractedEntity.confidence >= self.ner_config.confidence_threshold
            )
            .order_by((ExtractedEntity.confidence * ExtractedEntity.frequency).desc())
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _aggregate_entities_by_domain(
        self, contents: List[WebsiteContent]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Aggregate entities by domain.

        Enhanced in v6.0.0 to filter by extraction method and entity types.

        Args:
            contents: List of WebsiteContent objects

        Returns:
            Dictionary mapping domain to list of aggregated entity data
        """
        from urllib.parse import urlparse

        # Group contents by domain
        domain_content_ids = defaultdict(list)
        for content in contents:
            # Extract domain from URL
            parsed = urlparse(content.url)
            domain = parsed.netloc or parsed.path.split("/")[0]
            domain_content_ids[domain].append(content.id)

        # Load and aggregate entities for each domain
        domain_entities = {}

        for domain, content_ids in domain_content_ids.items():
            # Load all entities for this domain's contents with filtering
            stmt = (
                select(ExtractedEntity)
                .where(ExtractedEntity.website_content_id.in_(content_ids))
                .where(
                    ExtractedEntity.extraction_method
                    == self.ner_config.extraction_method
                )
                .where(ExtractedEntity.label.in_(self.ner_config.entity_types))
                .where(
                    ExtractedEntity.confidence >= self.ner_config.confidence_threshold
                )
            )

            result = await self.session.execute(stmt)
            entities = list(result.scalars().all())

            # Aggregate by entity text and label
            entity_stats = defaultdict(
                lambda: {
                    "total_frequency": 0,
                    "total_confidence": 0.0,
                    "count": 0,
                    "language": None,
                    "extraction_method": None,
                }
            )

            for entity in entities:
                # Use (text, label) as key to distinguish same text with different types
                key = (entity.text, entity.label)
                stats = entity_stats[key]
                stats["total_frequency"] += entity.frequency
                stats["total_confidence"] += entity.confidence
                stats["count"] += 1
                if stats["language"] is None:
                    stats["language"] = entity.language
                if stats["extraction_method"] is None:
                    stats["extraction_method"] = entity.extraction_method

            # Convert to list and calculate averages
            aggregated = []
            for (text, label), stats in entity_stats.items():
                aggregated.append(
                    {
                        "text": text,
                        "label": label,
                        "total_frequency": stats["total_frequency"],
                        "avg_confidence": stats["total_confidence"] / stats["count"],
                        "content_count": stats["count"],
                        "language": stats["language"],
                        "extraction_method": stats["extraction_method"],
                    }
                )

            # Sort by confidence * frequency (importance score)
            aggregated.sort(
                key=lambda x: x["avg_confidence"] * x["total_frequency"], reverse=True
            )

            domain_entities[domain] = aggregated

        return domain_entities

    async def get_top_entities(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get top N entities by degree (number of websites they appear in).

        Args:
            top_n: Number of top entities to return

        Returns:
            List of entity dictionaries
        """
        if self.graph is None:
            return []

        entities = []
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") == "entity":
                degree = self.graph.degree(node)

                # Calculate average weight
                edges = self.graph.edges(node, data=True)
                weights = [d.get("weight", 1.0) for _, _, d in edges]
                avg_weight = sum(weights) / len(weights) if weights else 0

                entities.append(
                    {
                        "text": data.get("entity_text"),
                        "label": data.get("entity_label"),
                        "language": data.get("language"),
                        "degree": degree,
                        "avg_weight": avg_weight,
                        "extraction_method": data.get("extraction_method"),
                    }
                )

        # Sort by degree
        entities.sort(key=lambda x: x["degree"], reverse=True)

        return entities[:top_n]

    async def get_top_websites(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get top N websites by degree (number of entities).

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

    async def get_entities_by_type(self) -> Dict[str, int]:
        """
        Get count of entities grouped by type.

        Returns:
            Dictionary mapping entity type to count
        """
        if self.graph is None:
            return {}

        entity_type_counts = defaultdict(int)
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") == "entity":
                entity_label = data.get("entity_label", "UNKNOWN")
                entity_type_counts[entity_label] += 1

        return dict(entity_type_counts)
