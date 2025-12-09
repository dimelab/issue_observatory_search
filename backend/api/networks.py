"""Network API endpoints for Phase 6."""
import logging
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.utils.dependencies import CurrentUser
from backend.models.user import User
from backend.services.network_service import NetworkService
from backend.schemas.network import (
    NetworkGenerateRequest,
    NetworkResponse,
    NetworkListResponse,
    NetworkGenerationTaskResponse,
    NetworkStatistics,
)
from backend.tasks.network_tasks import generate_network_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/networks", tags=["networks"])


@router.post(
    "/generate",
    response_model=NetworkGenerationTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate network from sessions",
    description="Generate a network graph from one or more search sessions. "
                "Returns a task ID for tracking async generation.",
)
async def generate_network(
    request: NetworkGenerateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a network from search sessions.

    This endpoint starts an async task to generate the network.
    Use the returned task_id to check generation progress.

    Network types (v6.0.0):
    - search_website: Bipartite network of queries → websites
    - website_noun: Legacy support (same as website_keyword with method='noun')
    - website_keyword: Bipartite network of websites → keywords (enhanced with multiple methods)
    - website_ner: Bipartite network of websites → named entities (NEW)
    - website_concept: Bipartite network of websites → concepts (LLM-based, not yet implemented)

    Keyword extraction methods (website_keyword):
    - noun: Original noun-only extraction (backward compatible)
    - all_pos: Nouns, verbs, adjectives
    - tfidf: TF-IDF with bigrams and IDF weighting
    - rake: RAKE algorithm with n-gram phrases
    """
    logger.info(
        f"Network generation request: type={request.type}, "
        f"name={request.name}, user={current_user.id}"
    )

    # Validate network type
    if request.type == "website_concept":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Website-concept networks require LLM integration (Phase 7). "
                   "Use 'search_website', 'website_keyword', or 'website_ner' instead.",
        )

    # Handle legacy website_noun type (backward compatibility)
    network_type = request.type
    if request.type == "website_noun":
        logger.info("Converting legacy 'website_noun' type to 'website_keyword' with method='noun'")
        network_type = "website_keyword"
        # If no keyword_config provided, create one with legacy settings
        if not request.keyword_config:
            from backend.schemas.analysis import KeywordExtractionConfig
            request.keyword_config = KeywordExtractionConfig(
                method="noun",
                max_keywords=request.top_n_nouns or 50,
                min_frequency=2
            )

    # Build configuration
    config = {
        "top_n_nouns": request.top_n_nouns,  # Legacy field
        "languages": request.languages,
        "min_tfidf_score": request.min_tfidf_score,  # Legacy field
        "aggregate_by_domain": request.aggregate_by_domain,
        "weight_method": request.weight_method,
    }

    # Add keyword extraction config (for website_keyword networks)
    if request.keyword_config:
        config["keyword_config"] = request.keyword_config.model_dump()

    # Add NER extraction config (for website_ner networks)
    if request.ner_config:
        config["ner_config"] = request.ner_config.model_dump()

    # Validate configurations based on network type
    if network_type == "website_keyword" and not request.keyword_config:
        # Use default keyword config
        from backend.schemas.analysis import KeywordExtractionConfig
        config["keyword_config"] = KeywordExtractionConfig().model_dump()

    if network_type == "website_ner" and not request.ner_config:
        # Use default NER config
        from backend.schemas.analysis import NERExtractionConfig
        config["ner_config"] = NERExtractionConfig().model_dump()

    if request.backboning:
        config["backboning"] = request.backboning.model_dump()

    # Start async task (use converted network_type for legacy support)
    task = generate_network_task.delay(
        user_id=current_user.id,
        name=request.name,
        network_type=network_type,  # Use converted type (website_noun → website_keyword)
        session_ids=request.session_ids,
        config=config,
    )

    logger.info(f"Started network generation task: {task.id}")

    return NetworkGenerationTaskResponse(
        task_id=task.id,
        status="pending",
        message="Network generation started. Use the task ID to check progress.",
    )


@router.get(
    "",
    response_model=NetworkListResponse,
    summary="List user's networks",
    description="Get a paginated list of networks for the current user.",
)
async def list_networks(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    type: Optional[str] = Query(None, description="Filter by network type"),
    session_id: Optional[int] = Query(None, description="Filter by session ID"),
):
    """
    List networks for the current user.

    Supports pagination and filtering by network type or session ID.
    """
    service = NetworkService(db)

    networks, total = await service.list_user_networks(
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        network_type=type,
        session_id=session_id,
    )

    return NetworkListResponse(
        total=total,
        page=page,
        per_page=per_page,
        networks=[NetworkResponse.model_validate(n) for n in networks],
    )


@router.get(
    "/{network_id}",
    response_model=NetworkResponse,
    summary="Get network details",
    description="Get detailed information about a specific network.",
)
async def get_network(
    network_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Get network details by ID.

    Returns comprehensive metadata including node/edge counts,
    backboning statistics, and generation parameters.
    """
    service = NetworkService(db)
    network = await service.get_network_by_id(network_id)

    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} not found",
        )

    # Check ownership
    if network.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this network",
        )

    return NetworkResponse.model_validate(network)


@router.get(
    "/{network_id}/download",
    response_class=FileResponse,
    summary="Download network file",
    description="Download the network file in various formats (GEXF, CSV, GraphML, JSON).",
)
async def download_network(
    network_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    format: str = Query("gexf", description="Export format: gexf, csv, graphml, json"),
):
    """
    Download network file in specified format.

    Formats:
    - gexf: Gephi-compatible format (default)
    - csv: Simple edge list with Source,Target,Weight columns
    - graphml: GraphML format
    - json: JSON node-link format
    """
    import networkx as nx
    import tempfile
    from backend.core.networks.exporters import export_graph

    service = NetworkService(db)
    network = await service.get_network_by_id(network_id)

    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} not found",
        )

    # Check ownership
    if network.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this network",
        )

    # Check file exists
    file_path = Path(network.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network file not found",
        )

    # If requesting GEXF and it exists, return original file
    if format == "gexf":
        filename = f"{network.name}_{network.id}.gexf"
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/xml",
        )

    # For other formats, load graph and export
    try:
        # Load graph from GEXF
        graph = nx.read_gexf(str(file_path))

        # Create temporary file for export
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=f'.{format}',
            delete=False
        ) as temp_file:
            temp_path = temp_file.name

        # Export to requested format
        export_graph(graph, temp_path, format=format)

        # Determine media type
        media_types = {
            "csv": "text/csv",
            "graphml": "application/xml",
            "json": "application/json",
        }
        media_type = media_types.get(format, "application/octet-stream")

        # Return file
        filename = f"{network.name}_{network.id}.{format}"
        return FileResponse(
            path=temp_path,
            filename=filename,
            media_type=media_type,
        )

    except Exception as e:
        logger.error(f"Error exporting network {network_id} to {format}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export network in {format} format",
        )


@router.get(
    "/{network_id}/statistics",
    response_model=NetworkStatistics,
    summary="Get network statistics",
    description="Get detailed graph statistics for a network.",
)
async def get_network_statistics(
    network_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed network statistics.

    Returns graph metrics including density, degree distribution,
    connected components, and weight statistics.
    """
    service = NetworkService(db)
    network = await service.get_network_by_id(network_id)

    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} not found",
        )

    # Check ownership
    if network.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this network",
        )

    # Get statistics
    stats = await service.get_network_statistics(network_id)

    # Convert to response schema
    return NetworkStatistics(
        node_count=stats["node_count"],
        edge_count=stats["edge_count"],
        density=stats.get("metadata", {}).get("density", 0.0),
        avg_degree=stats.get("metadata", {}).get("avg_degree", 0.0),
        min_degree=stats.get("metadata", {}).get("min_degree", 0),
        max_degree=stats.get("metadata", {}).get("max_degree", 0),
        node_types=stats.get("metadata", {}).get("node_types", {}),
        connected_components=stats.get("metadata", {}).get("connected_components"),
        largest_component_size=stats.get("metadata", {}).get("largest_component_size"),
        avg_weight=stats.get("metadata", {}).get("avg_weight"),
        min_weight=stats.get("metadata", {}).get("min_weight"),
        max_weight=stats.get("metadata", {}).get("max_weight"),
    )


@router.delete(
    "/{network_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete network",
    description="Delete a network and its associated file.",
)
async def delete_network(
    network_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a network.

    Removes both the database record and the GEXF file.
    """
    service = NetworkService(db)
    network = await service.get_network_by_id(network_id)

    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network {network_id} not found",
        )

    # Check ownership
    if network.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this network",
        )

    # Delete
    deleted = await service.delete_network(network_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete network",
        )

    logger.info(f"Deleted network {network_id} for user {current_user.id}")

    return None
