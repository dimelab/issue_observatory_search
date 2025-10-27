"""Celery tasks for network generation."""
import logging
from typing import Dict, Any, List, Optional
from celery import Task

from backend.celery_app import celery_app
from backend.database import AsyncSessionLocal
from backend.services.network_service import NetworkService
from backend.schemas.network import NetworkBackboningConfig
from backend.config import settings

logger = logging.getLogger(__name__)


class NetworkGenerationTask(Task):
    """Base task for network generation with error handling."""

    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True


@celery_app.task(
    bind=True,
    base=NetworkGenerationTask,
    name="tasks.generate_network",
    soft_time_limit=600,  # 10 minutes
    time_limit=900,  # 15 minutes
)
def generate_network_task(
    self,
    user_id: int,
    name: str,
    network_type: str,
    session_ids: List[int],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate network asynchronously.

    Args:
        self: Celery task instance
        user_id: User ID
        name: Network name
        network_type: Type of network (search_website, website_noun, etc.)
        session_ids: List of session IDs
        config: Network configuration dictionary

    Returns:
        Dictionary with network_id and statistics
    """
    logger.info(
        f"Starting network generation task: type={network_type}, "
        f"name={name}, user={user_id}"
    )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "current": 0,
            "total": 100,
            "status": "Initializing network generation...",
        },
    )

    async def _generate():
        async with AsyncSessionLocal() as session:
            service = NetworkService(session)

            try:
                # Update state
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": 10,
                        "total": 100,
                        "status": "Building network graph...",
                    },
                )

                # Parse backboning config if present
                backboning_config = None
                if config.get("backboning"):
                    backboning_config = NetworkBackboningConfig(
                        **config["backboning"]
                    )

                # Generate based on type
                if network_type == "search_website":
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": 30,
                            "total": 100,
                            "status": "Generating search-website network...",
                        },
                    )

                    network = await service.generate_search_website_network(
                        user_id=user_id,
                        name=name,
                        session_ids=session_ids,
                        weight_method=config.get("weight_method", "inverse_rank"),
                        aggregate_by_domain=config.get("aggregate_by_domain", True),
                        backboning_config=backboning_config,
                    )

                elif network_type == "website_noun":
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": 30,
                            "total": 100,
                            "status": "Generating website-noun network...",
                        },
                    )

                    network = await service.generate_website_noun_network(
                        user_id=user_id,
                        name=name,
                        session_ids=session_ids,
                        top_n_nouns=config.get("top_n_nouns", 50),
                        languages=config.get("languages"),
                        min_tfidf_score=config.get("min_tfidf_score", 0.0),
                        aggregate_by_domain=config.get("aggregate_by_domain", True),
                        backboning_config=backboning_config,
                    )

                elif network_type == "website_concept":
                    raise NotImplementedError(
                        "Website-concept networks require LLM integration (Phase 7)"
                    )

                else:
                    raise ValueError(f"Unknown network type: {network_type}")

                # Update state
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": 90,
                        "total": 100,
                        "status": "Finalizing export...",
                    },
                )

                logger.info(
                    f"Network generation complete: id={network.id}, "
                    f"nodes={network.node_count}, edges={network.edge_count}"
                )

                return {
                    "network_id": network.id,
                    "name": network.name,
                    "type": network.type,
                    "node_count": network.node_count,
                    "edge_count": network.edge_count,
                    "file_size": network.file_size,
                    "backboning_applied": network.backboning_applied,
                }

            except Exception as e:
                logger.error(f"Network generation failed: {e}", exc_info=True)
                raise

    # Run async function
    import asyncio
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(_generate())

    return result


@celery_app.task(
    name="tasks.cleanup_old_networks",
    soft_time_limit=300,  # 5 minutes
    time_limit=600,  # 10 minutes
)
def cleanup_old_networks_task(days: Optional[int] = None) -> Dict[str, Any]:
    """
    Clean up old network exports.

    Args:
        days: Delete networks older than this many days
              (defaults to config setting)

    Returns:
        Dictionary with cleanup statistics
    """
    if days is None:
        days = settings.network_cleanup_days

    logger.info(f"Starting cleanup of networks older than {days} days")

    async def _cleanup():
        async with AsyncSessionLocal() as session:
            service = NetworkService(session)
            deleted_count = await service.cleanup_old_networks(days=days)
            return {"deleted_count": deleted_count, "days": days}

    import asyncio
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(_cleanup())

    logger.info(f"Cleanup complete: deleted {result['deleted_count']} networks")

    return result


@celery_app.task(
    name="tasks.recalculate_network_statistics",
    soft_time_limit=300,
    time_limit=600,
)
def recalculate_network_statistics_task(network_id: int) -> Dict[str, Any]:
    """
    Recalculate statistics for a network by reloading the file.

    Args:
        network_id: Network ID

    Returns:
        Dictionary with updated statistics
    """
    logger.info(f"Recalculating statistics for network {network_id}")

    async def _recalculate():
        async with AsyncSessionLocal() as session:
            service = NetworkService(session)

            # Get network
            network = await service.get_network_by_id(network_id)
            if not network:
                raise ValueError(f"Network {network_id} not found")

            # Load graph from file
            import networkx as nx
            from pathlib import Path

            file_path = Path(network.file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Network file not found: {file_path}")

            # Load graph
            graph = nx.read_gexf(str(file_path))

            # Calculate statistics
            from backend.core.networks.graph_utils import calculate_graph_metrics
            stats = calculate_graph_metrics(graph)

            # Update database
            await service.repository.update_statistics(
                network_id=network_id,
                node_count=stats["node_count"],
                edge_count=stats["edge_count"],
                file_size=file_path.stat().st_size,
            )

            await session.commit()

            return stats

    import asyncio
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(_recalculate())

    logger.info(f"Statistics recalculated for network {network_id}")

    return result
