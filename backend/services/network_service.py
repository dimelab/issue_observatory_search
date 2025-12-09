"""Network service for Phase 6.

Enhanced in v6.0.0:
- Support for website_keyword networks with multiple extraction methods
- Support for website_ner networks (named entity recognition)
"""
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import os

import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.repositories.network_repository import NetworkRepository
from backend.core.networks.search_website import SearchWebsiteNetworkBuilder
from backend.core.networks.website_noun import WebsiteNounNetworkBuilder
from backend.core.networks.website_ner import WebsiteNERNetworkBuilder
from backend.core.networks.website_concept import WebsiteConceptNetworkBuilder
from backend.core.networks.graph_utils import calculate_graph_metrics
from backend.core.networks.backboning import apply_backboning
from backend.core.networks.exporters import export_to_gexf
from backend.models.network import NetworkExport
from backend.schemas.network import NetworkBackboningConfig
from backend.schemas.analysis import KeywordExtractionConfig, NERExtractionConfig

logger = logging.getLogger(__name__)


class NetworkService:
    """
    Service for network generation and management.

    Handles network building, backboning, export, and lifecycle management.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the network service.

        Args:
            session: Database session
        """
        self.session = session
        self.repository = NetworkRepository(session)

    async def generate_search_website_network(
        self,
        user_id: int,
        name: str,
        session_ids: List[int],
        weight_method: str = "inverse_rank",
        aggregate_by_domain: bool = True,
        backboning_config: Optional[NetworkBackboningConfig] = None,
    ) -> NetworkExport:
        """
        Generate search-website bipartite network.

        Args:
            user_id: User ID
            name: Network name
            session_ids: List of search session IDs
            weight_method: Edge weight calculation method
            aggregate_by_domain: Whether to aggregate by domain
            backboning_config: Optional backboning configuration

        Returns:
            NetworkExport object
        """
        logger.info(
            f"Generating search-website network: name={name}, "
            f"sessions={session_ids}, user={user_id}"
        )

        # Build network
        builder = SearchWebsiteNetworkBuilder(
            name=name,
            session=self.session,
            session_ids=session_ids,
            weight_method=weight_method,
            aggregate_by_domain=aggregate_by_domain,
        )

        graph = await builder.build()

        # Validate graph
        if graph.number_of_nodes() == 0:
            raise ValueError("Generated network has no nodes. Check session data.")

        # Apply backboning if configured
        backboning_stats = None
        original_edge_count = graph.number_of_edges()

        if backboning_config and backboning_config.enabled:
            graph, backboning_stats = await self._apply_backboning(
                graph, backboning_config
            )

        # Export to GEXF
        file_path = await self._generate_file_path(user_id, name, "gexf")
        export_stats = export_to_gexf(graph, file_path)

        # Create database record
        metadata = builder.metadata
        metadata.update({
            "weight_method": weight_method,
            "aggregate_by_domain": aggregate_by_domain,
        })

        network = await self.repository.create_export(
            user_id=user_id,
            name=name,
            network_type="search_website",
            session_ids=session_ids,
            file_path=file_path,
            file_size=export_stats["file_size"],
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
            network_metadata=metadata,
            backboning_applied=backboning_config.enabled if backboning_config else False,
            backboning_algorithm=(
                backboning_config.algorithm if backboning_config and backboning_config.enabled else None
            ),
            backboning_alpha=(
                backboning_config.alpha if backboning_config and backboning_config.enabled else None
            ),
            original_edge_count=original_edge_count,
            backboning_statistics=backboning_stats,
        )

        await self.session.commit()

        logger.info(
            f"Generated search-website network: id={network.id}, "
            f"nodes={network.node_count}, edges={network.edge_count}"
        )

        return network

    async def generate_website_noun_network(
        self,
        user_id: int,
        name: str,
        session_ids: List[int],
        top_n_nouns: int = 50,
        languages: Optional[List[str]] = None,
        min_tfidf_score: float = 0.0,
        aggregate_by_domain: bool = True,
        backboning_config: Optional[NetworkBackboningConfig] = None,
        keyword_config: Optional[KeywordExtractionConfig] = None,  # v6.0.0
    ) -> NetworkExport:
        """
        Generate website-keyword (noun) bipartite network.

        Enhanced in v6.0.0 to support multiple extraction methods via keyword_config.

        Args:
            user_id: User ID
            name: Network name
            session_ids: List of search session IDs
            top_n_nouns: Top N keywords per website (kept for backward compat)
            languages: Language filter
            min_tfidf_score: Minimum TF-IDF score
            aggregate_by_domain: Whether to aggregate by domain
            backboning_config: Optional backboning configuration
            keyword_config: v6.0.0 - Configuration for keyword extraction filtering

        Returns:
            NetworkExport object
        """
        logger.info(
            f"Generating website-keyword network: name={name}, "
            f"sessions={session_ids}, user={user_id}, "
            f"method={keyword_config.method if keyword_config else 'noun'}"
        )

        # Check if analysis is needed and trigger it
        await self._ensure_content_analyzed(session_ids)

        # Build network
        builder = WebsiteNounNetworkBuilder(
            name=name,
            session=self.session,
            session_ids=session_ids,
            top_n_nouns=top_n_nouns,
            languages=languages,
            min_tfidf_score=min_tfidf_score,
            aggregate_by_domain=aggregate_by_domain,
            keyword_config=keyword_config,  # v6.0.0
        )

        graph = await builder.build()

        # Validate graph
        if graph.number_of_nodes() == 0:
            raise ValueError("Generated network has no nodes. Check session data.")

        # Apply backboning if configured
        backboning_stats = None
        original_edge_count = graph.number_of_edges()

        if backboning_config and backboning_config.enabled:
            graph, backboning_stats = await self._apply_backboning(
                graph, backboning_config
            )

        # Export to GEXF
        file_path = await self._generate_file_path(user_id, name, "gexf")
        export_stats = export_to_gexf(graph, file_path)

        # Create database record
        metadata = builder.metadata

        network = await self.repository.create_export(
            user_id=user_id,
            name=name,
            network_type="website_noun",
            session_ids=session_ids,
            file_path=file_path,
            file_size=export_stats["file_size"],
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
            network_metadata=metadata,
            backboning_applied=backboning_config.enabled if backboning_config else False,
            backboning_algorithm=(
                backboning_config.algorithm if backboning_config and backboning_config.enabled else None
            ),
            backboning_alpha=(
                backboning_config.alpha if backboning_config and backboning_config.enabled else None
            ),
            original_edge_count=original_edge_count,
            backboning_statistics=backboning_stats,
        )

        await self.session.commit()

        logger.info(
            f"Generated website-noun network: id={network.id}, "
            f"nodes={network.node_count}, edges={network.edge_count}"
        )

        return network

    async def generate_website_ner_network(
        self,
        user_id: int,
        name: str,
        session_ids: List[int],
        top_n_entities: int = 50,
        languages: Optional[List[str]] = None,
        min_confidence: float = 0.85,
        aggregate_by_domain: bool = True,
        backboning_config: Optional[NetworkBackboningConfig] = None,
        ner_config: Optional[NERExtractionConfig] = None,  # v6.0.0
    ) -> NetworkExport:
        """
        Generate website-NER bipartite network.

        New in v6.0.0: Build networks connecting websites to named entities.

        Args:
            user_id: User ID
            name: Network name
            session_ids: List of search session IDs
            top_n_entities: Top N entities per website
            languages: Language filter
            min_confidence: Minimum confidence score
            aggregate_by_domain: Whether to aggregate by domain
            backboning_config: Optional backboning configuration
            ner_config: v6.0.0 - Configuration for NER extraction filtering

        Returns:
            NetworkExport object
        """
        logger.info(
            f"Generating website-NER network: name={name}, "
            f"sessions={session_ids}, user={user_id}, "
            f"method={ner_config.extraction_method if ner_config else 'spacy'}"
        )

        # Check if analysis is needed and trigger it
        await self._ensure_content_analyzed(session_ids)

        # Build network
        builder = WebsiteNERNetworkBuilder(
            name=name,
            session=self.session,
            session_ids=session_ids,
            top_n_entities=top_n_entities,
            languages=languages,
            min_confidence=min_confidence,
            aggregate_by_domain=aggregate_by_domain,
            ner_config=ner_config,  # v6.0.0
        )

        graph = await builder.build()

        # Validate graph
        if graph.number_of_nodes() == 0:
            raise ValueError("Generated network has no nodes. Check session data.")

        # Apply backboning if configured
        backboning_stats = None
        original_edge_count = graph.number_of_edges()

        if backboning_config and backboning_config.enabled:
            graph, backboning_stats = await self._apply_backboning(
                graph, backboning_config
            )

        # Export to GEXF
        file_path = await self._generate_file_path(user_id, name, "gexf")
        export_stats = export_to_gexf(graph, file_path)

        # Create database record
        metadata = builder.metadata

        network = await self.repository.create_export(
            user_id=user_id,
            name=name,
            network_type="website_ner",
            session_ids=session_ids,
            file_path=file_path,
            file_size=export_stats["file_size"],
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
            network_metadata=metadata,
            backboning_applied=backboning_config.enabled if backboning_config else False,
            backboning_algorithm=(
                backboning_config.algorithm if backboning_config and backboning_config.enabled else None
            ),
            backboning_alpha=(
                backboning_config.alpha if backboning_config and backboning_config.enabled else None
            ),
            original_edge_count=original_edge_count,
            backboning_statistics=backboning_stats,
        )

        await self.session.commit()

        logger.info(
            f"Generated website-NER network: id={network.id}, "
            f"nodes={network.node_count}, edges={network.edge_count}"
        )

        return network

    async def generate_website_concept_network(
        self,
        user_id: int,
        name: str,
        session_ids: List[int],
        **kwargs,
    ) -> NetworkExport:
        """
        Generate website-concept bipartite network.

        NOT YET IMPLEMENTED - placeholder for LLM integration.

        Args:
            user_id: User ID
            name: Network name
            session_ids: List of search session IDs
            **kwargs: Additional parameters

        Returns:
            NetworkExport object

        Raises:
            NotImplementedError: Always, as this requires LLM integration
        """
        raise NotImplementedError(
            "Website-Concept network generation requires LLM integration. "
            "This feature will be implemented in Phase 7 (LLM Integration)."
        )

    async def get_network_statistics(
        self,
        network_id: int,
    ) -> Dict[str, Any]:
        """
        Get detailed statistics for a network.

        Args:
            network_id: Network ID

        Returns:
            Dictionary of statistics
        """
        network = await self.repository.get_by_id(network_id)

        if not network:
            raise ValueError(f"Network {network_id} not found")

        # Basic stats from database
        stats = {
            "id": network.id,
            "name": network.name,
            "type": network.type,
            "node_count": network.node_count,
            "edge_count": network.edge_count,
            "file_size": network.file_size,
            "backboning_applied": network.backboning_applied,
            "created_at": network.created_at.isoformat(),
        }

        # Add backboning stats if available
        if network.backboning_applied and network.backboning_statistics:
            stats["backboning"] = network.backboning_statistics

        # Add metadata
        stats["metadata"] = network.metadata

        return stats

    async def list_user_networks(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
        network_type: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> tuple[List[NetworkExport], int]:
        """
        List networks for a user with pagination.

        Args:
            user_id: User ID
            page: Page number
            per_page: Results per page
            network_type: Optional filter by type
            session_id: Optional filter by session

        Returns:
            Tuple of (networks list, total count)
        """
        return await self.repository.get_by_user(
            user_id=user_id,
            page=page,
            per_page=per_page,
            network_type=network_type,
            session_id=session_id,
        )

    async def delete_network(
        self,
        network_id: int,
    ) -> bool:
        """
        Delete a network and its file.

        Args:
            network_id: Network ID

        Returns:
            True if deleted successfully
        """
        # Get network
        network = await self.repository.get_by_id(network_id)

        if not network:
            return False

        # Delete file
        try:
            file_path = Path(network.file_path)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted network file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete network file: {e}")
            # Continue with database deletion even if file deletion fails

        # Delete database record
        deleted = await self.repository.delete_export(network_id)

        if deleted:
            await self.session.commit()

        return deleted

    async def cleanup_old_networks(
        self,
        days: int = 30,
    ) -> int:
        """
        Clean up old network exports.

        Args:
            days: Delete networks older than this many days

        Returns:
            Number of networks deleted
        """
        old_networks = await self.repository.get_old_exports(days=days)

        deleted_count = 0
        for network in old_networks:
            try:
                success = await self.delete_network(network.id)
                if success:
                    deleted_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to delete old network {network.id}: {e}"
                )

        logger.info(
            f"Cleaned up {deleted_count} old network exports (older than {days} days)"
        )

        return deleted_count

    async def _apply_backboning(
        self,
        graph: nx.Graph,
        config: NetworkBackboningConfig,
    ) -> tuple[nx.Graph, Dict[str, Any]]:
        """
        Apply backboning algorithm to graph.

        Args:
            graph: NetworkX graph
            config: Backboning configuration

        Returns:
            Tuple of (backboned graph, statistics)
        """
        logger.info(
            f"Applying backboning: algorithm={config.algorithm}, alpha={config.alpha}"
        )

        kwargs = {}

        if config.algorithm == "disparity_filter":
            kwargs["alpha"] = config.alpha or 0.05
            if config.min_edge_weight is not None:
                kwargs["min_edge_weight"] = config.min_edge_weight

        elif config.algorithm == "threshold":
            if config.threshold is None:
                raise ValueError("threshold parameter required for threshold filter")
            kwargs["threshold"] = config.threshold

        elif config.algorithm == "top_k":
            if config.k is None:
                raise ValueError("k parameter required for top_k filter")
            kwargs["k"] = config.k

        backboned_graph, stats = apply_backboning(
            graph,
            algorithm=config.algorithm,
            **kwargs,
        )

        return backboned_graph, stats

    async def _generate_file_path(
        self,
        user_id: int,
        name: str,
        extension: str,
    ) -> str:
        """
        Generate file path for network export.

        Args:
            user_id: User ID
            name: Network name
            extension: File extension

        Returns:
            File path string
        """
        # Create export directory
        export_dir = Path(settings.network_export_dir) / str(user_id)
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in name
        )
        filename = f"{safe_name}_{timestamp}.{extension}"

        file_path = export_dir / filename

        return str(file_path)

    async def _ensure_content_analyzed(self, session_ids: List[int]) -> None:
        """
        Ensure content from sessions is analyzed. Runs analysis inline if needed.

        Args:
            session_ids: List of session IDs to check
        """
        from sqlalchemy import select, func
        from backend.models.scraping import ScrapingJob
        from backend.models.website import WebsiteContent
        from backend.models.analysis import ExtractedNoun
        from backend.services.analysis_service import AnalysisService

        logger.info(f"Checking if content from sessions {session_ids} is analyzed")

        # Get scraping jobs for these sessions
        stmt_jobs = (
            select(ScrapingJob)
            .where(ScrapingJob.session_id.in_(session_ids))
            .where(ScrapingJob.status == "completed")
        )
        result = await self.session.execute(stmt_jobs)
        jobs = result.scalars().all()

        if not jobs:
            logger.warning(f"No completed scraping jobs found for sessions {session_ids}")
            return

        analysis_service = AnalysisService(self.session)

        # Check each job to see if it needs analysis
        for job in jobs:
            # Get unanalyzed content IDs
            stmt_unanalyzed = (
                select(WebsiteContent.id)
                .outerjoin(ExtractedNoun, WebsiteContent.id == ExtractedNoun.website_content_id)
                .where(
                    WebsiteContent.scraping_job_id == job.id,
                    WebsiteContent.status == 'success',
                    ExtractedNoun.id.is_(None)  # No analysis yet
                )
            )
            unanalyzed_result = await self.session.execute(stmt_unanalyzed)
            unanalyzed_ids = [row[0] for row in unanalyzed_result.all()]

            if unanalyzed_ids:
                logger.info(
                    f"Job {job.id} has {len(unanalyzed_ids)} unanalyzed pages. "
                    f"Running analysis inline..."
                )

                # Analyze each piece of content inline (not as separate tasks)
                for content_id in unanalyzed_ids:
                    try:
                        await analysis_service.analyze_content(
                            content_id=content_id,
                            extract_nouns=True,
                            extract_entities=True,
                            max_nouns=100,
                            min_frequency=2
                        )
                        logger.debug(f"Analyzed content {content_id}")
                    except Exception as e:
                        logger.error(f"Failed to analyze content {content_id}: {e}")

                # Commit all analysis results
                await self.session.commit()
                logger.info(f"Completed analysis for {len(unanalyzed_ids)} pages from job {job.id}")

    async def get_network_by_id(self, network_id: int) -> Optional[NetworkExport]:
        """
        Get network by ID.

        Args:
            network_id: Network ID

        Returns:
            NetworkExport object or None
        """
        return await self.repository.get_by_id(network_id)
