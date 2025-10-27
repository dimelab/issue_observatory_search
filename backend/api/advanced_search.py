"""Advanced search API endpoints for Phase 7 features."""
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.database import get_db
from backend.models.user import User
from backend.models.query_expansion import QueryExpansionCandidate
from backend.models.query_template import QueryTemplate, QueryFromTemplate
from backend.utils.dependencies import CurrentUser
from backend.schemas.advanced_search import (
    QueryExpansionRequest,
    QueryExpansionResponse,
    QueryExpansionCandidateResponse,
    ApproveExpansionRequest,
    ExecuteExpansionRequest,
    QueryTemplateCreate,
    QueryTemplateResponse,
    ApplyTemplateRequest,
    MultiPerspectiveRequest,
    SessionComparisonRequest,
    SessionComparisonResponse,
    TemporalSearchRequest,
    TemporalComparisonRequest,
)
from backend.services.search_service import SearchService
from backend.services.temporal_search_service import TemporalSearchService
from backend.services.session_comparison_service import SessionComparisonService
from backend.core.search.query_templates import QueryTemplateManager
from backend.tasks.advanced_search_tasks import query_expansion_task

router = APIRouter(prefix="/advanced-search", tags=["advanced-search"])
logger = logging.getLogger(__name__)


# Query Expansion Endpoints
@router.post("/expand", response_model=QueryExpansionResponse)
async def generate_query_expansions(
    request: QueryExpansionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Generate query expansion candidates from a session.

    Analyzes search results and scraped content to suggest related terms
    for snowballing the search.

    Args:
        request: Expansion parameters
        db: Database session
        current_user: Current user

    Returns:
        List of expansion candidates with scores
    """
    # Verify session ownership
    from backend.models.search import SearchSession

    session_result = await db.execute(
        select(SearchSession).where(
            and_(
                SearchSession.id == request.session_id,
                SearchSession.user_id == current_user.id,
            )
        )
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Start expansion task
    task = query_expansion_task.delay(
        session_id=request.session_id,
        user_id=current_user.id,
        expansion_sources=request.expansion_sources,
        max_candidates=request.max_candidates,
        min_score=request.min_score,
    )

    # Wait for task to complete (for now, synchronous)
    result = task.get(timeout=60)

    # Fetch generated candidates
    candidates_result = await db.execute(
        select(QueryExpansionCandidate)
        .where(QueryExpansionCandidate.session_id == request.session_id)
        .order_by(QueryExpansionCandidate.score.desc())
        .limit(request.max_candidates)
    )
    candidates = list(candidates_result.scalars().all())

    return QueryExpansionResponse(
        session_id=request.session_id,
        candidates=[
            QueryExpansionCandidateResponse.model_validate(c) for c in candidates
        ],
        total_candidates=len(candidates),
        sources_used=request.expansion_sources,
    )


@router.post("/expand/approve")
async def approve_expansion_candidates(
    request: ApproveExpansionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Approve or reject expansion candidates.

    Args:
        request: Approval request with candidate IDs
        db: Database session
        current_user: Current user

    Returns:
        Success message
    """
    # Get candidates
    candidates_result = await db.execute(
        select(QueryExpansionCandidate).where(
            QueryExpansionCandidate.id.in_(request.candidate_ids)
        )
    )
    candidates = list(candidates_result.scalars().all())

    if not candidates:
        raise HTTPException(status_code=404, detail="Candidates not found")

    # Update approval status
    from datetime import datetime

    for candidate in candidates:
        candidate.approved = request.approved
        candidate.approved_at = datetime.utcnow()
        candidate.approved_by_user_id = current_user.id

    await db.commit()

    action = "approved" if request.approved else "rejected"
    logger.info(f"User {current_user.id} {action} {len(candidates)} candidates")

    return {
        "message": f"Successfully {action} {len(candidates)} candidates",
        "candidate_ids": request.candidate_ids,
        "approved": request.approved,
    }


@router.post("/expand/execute")
async def execute_approved_expansions(
    request: ExecuteExpansionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Execute searches for approved expansion candidates.

    Args:
        request: Execution parameters
        db: Database session
        current_user: Current user

    Returns:
        Session with expansion results
    """
    # Get approved candidates
    candidates_result = await db.execute(
        select(QueryExpansionCandidate).where(
            and_(
                QueryExpansionCandidate.session_id == request.session_id,
                QueryExpansionCandidate.approved == True,
            )
        )
    )
    candidates = list(candidates_result.scalars().all())

    if not candidates:
        raise HTTPException(
            status_code=404, detail="No approved candidates found for this session"
        )

    # Get parent session
    from backend.models.search import SearchSession

    parent_session = await db.execute(
        select(SearchSession).where(SearchSession.id == request.session_id)
    )
    parent = parent_session.scalar_one()

    # Create new session for expansion results
    search_service = SearchService(db, current_user)
    expansion_session = await search_service.create_session(
        name=f"{parent.name} - Expansion Gen {request.generation}",
        description=f"Query expansion results (generation {request.generation})",
        config={"parent_session_id": request.session_id, "generation": request.generation},
    )

    # Execute searches for approved candidates
    queries = [c.candidate_term for c in candidates]

    await search_service.execute_search(
        session=expansion_session,
        queries=queries,
        search_engine=request.search_engine,
        max_results=request.max_results,
    )

    logger.info(
        f"Executed {len(queries)} expansion queries in session {expansion_session.id}"
    )

    return {
        "parent_session_id": request.session_id,
        "expansion_session_id": expansion_session.id,
        "queries_executed": len(queries),
        "generation": request.generation,
        "status": expansion_session.status,
    }


# Query Template Endpoints
@router.get("/templates", response_model=List[QueryTemplateResponse])
async def list_query_templates(
    language: str = Query("en", description="Language filter"),
    framing_type: str = Query(None, description="Framing type filter"),
    include_public: bool = Query(True, description="Include public templates"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    List available query templates.

    Args:
        language: Language filter
        framing_type: Optional framing type filter
        include_public: Include public templates
        db: Database session
        current_user: Current user

    Returns:
        List of query templates
    """
    # Build query
    conditions = [QueryTemplate.language == language]

    # Include user's own templates or public ones
    if include_public:
        conditions.append(
            (QueryTemplate.user_id == current_user.id) | (QueryTemplate.is_public == True)
        )
    else:
        conditions.append(QueryTemplate.user_id == current_user.id)

    if framing_type:
        conditions.append(QueryTemplate.framing_type == framing_type)

    result = await db.execute(select(QueryTemplate).where(and_(*conditions)))
    templates = list(result.scalars().all())

    return [QueryTemplateResponse.model_validate(t) for t in templates]


@router.post("/templates", response_model=QueryTemplateResponse)
async def create_query_template(
    template: QueryTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Create a custom query template.

    Args:
        template: Template data
        db: Database session
        current_user: Current user

    Returns:
        Created template
    """
    # Extract variables from template
    template_manager = QueryTemplateManager()
    variables = template_manager.get_template_variables(template.template)

    # Create template
    db_template = QueryTemplate(
        user_id=current_user.id,
        name=template.name,
        framing_type=template.framing_type,
        template=template.template,
        variables={"required": variables},
        language=template.language,
        is_public=template.is_public,
        description=template.description,
    )

    db.add(db_template)
    await db.commit()
    await db.refresh(db_template)

    logger.info(f"Created query template: {template.name}")

    return QueryTemplateResponse.model_validate(db_template)


@router.post("/templates/{template_id}/apply")
async def apply_query_template(
    template_id: int,
    request: ApplyTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Apply a query template with variable substitutions.

    Args:
        template_id: Template ID
        request: Substitution parameters
        db: Database session
        current_user: Current user

    Returns:
        Session with template results
    """
    # Get template
    template_result = await db.execute(
        select(QueryTemplate).where(QueryTemplate.id == template_id)
    )
    template = template_result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check access
    if template.user_id != current_user.id and not template.is_public:
        raise HTTPException(status_code=403, detail="Access denied to this template")

    # Apply template
    try:
        query_text = template.template.format(**request.substitutions)
    except KeyError as e:
        raise HTTPException(
            status_code=400, detail=f"Missing required variable: {e}"
        )

    # Create session if requested
    search_service = SearchService(db, current_user)

    if request.create_session:
        session_name = request.session_name or f"Template: {template.name}"
        session = await search_service.create_session(
            name=session_name,
            description=f"Generated from template: {template.name}",
            config={"template_id": template_id},
        )

        # Execute search
        await search_service.execute_search(
            session=session,
            queries=[query_text],
            search_engine=request.search_engine,
            max_results=request.max_results,
        )

        # Record template usage
        usage = QueryFromTemplate(
            template_id=template_id,
            search_query_id=session.queries[0].id if session.queries else None,
            substitutions=request.substitutions,
        )
        db.add(usage)
        await db.commit()

        return {
            "session_id": session.id,
            "query": query_text,
            "template_id": template_id,
            "status": session.status,
        }
    else:
        # Just return the generated query
        return {"query": query_text, "template_id": template_id}


@router.post("/multi-perspective")
async def generate_multi_perspective_search(
    request: MultiPerspectiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Generate and execute multi-perspective search queries.

    Creates queries representing different framings (neutral, activist,
    skeptic, scientific, etc.) of the same issue.

    Args:
        request: Multi-perspective parameters
        db: Database session
        current_user: Current user

    Returns:
        Sessions for each framing
    """
    # Generate queries
    template_manager = QueryTemplateManager()
    framing_queries = template_manager.generate_multi_perspective_queries(
        issue=request.issue,
        language=request.language,
        framings=request.framings,
        location=request.location,
        year=request.year,
    )

    # Create sessions for each framing
    search_service = SearchService(db, current_user)
    results = {}

    for framing_type, queries in framing_queries.items():
        session_name = (
            request.session_name or f"{request.issue} - {framing_type} framing"
        )

        session = await search_service.create_session(
            name=session_name,
            description=f"Multi-perspective search: {framing_type} framing",
            config={
                "multi_perspective": True,
                "framing": framing_type,
                "issue": request.issue,
            },
        )

        # Execute searches
        await search_service.execute_search(
            session=session,
            queries=queries[:10],  # Limit queries per framing
            search_engine=request.search_engine,
            max_results=request.max_results,
        )

        results[framing_type] = {
            "session_id": session.id,
            "queries": queries[:10],
            "status": session.status,
        }

    logger.info(
        f"Generated multi-perspective search for '{request.issue}' "
        f"with {len(results)} framings"
    )

    return {
        "issue": request.issue,
        "language": request.language,
        "framings": results,
        "total_sessions": len(results),
    }


# Session Comparison Endpoints
@router.post("/sessions/compare", response_model=SessionComparisonResponse)
async def compare_sessions(
    request: SessionComparisonRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Compare multiple search sessions.

    Provides comprehensive comparison including URL overlap, domain
    distribution, ranking differences, and discourse analysis.

    Args:
        request: Comparison parameters
        db: Database session
        current_user: Current user

    Returns:
        Comparison results
    """
    comparison_service = SessionComparisonService(db, current_user)

    try:
        results = await comparison_service.compare_sessions(
            session_ids=request.session_ids,
            comparison_type=request.comparison_type,
        )

        return SessionComparisonResponse(**results)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Temporal Search Endpoints
@router.post("/temporal/search")
async def execute_temporal_search(
    request: TemporalSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Execute search with date range filtering.

    Args:
        request: Temporal search parameters
        db: Database session
        current_user: Current user

    Returns:
        Session with temporal results
    """
    search_service = SearchService(db, current_user)
    temporal_service = TemporalSearchService(db, current_user)

    # Create session
    session = await search_service.create_session(
        name=request.session_name,
        description=f"Temporal search: {request.date_from} to {request.date_to}",
    )

    # Execute temporal search
    await temporal_service.search_with_date_range(
        session=session,
        queries=request.queries,
        search_engine=request.search_engine,
        max_results=request.max_results,
        date_from=request.date_from,
        date_to=request.date_to,
        temporal_snapshot=request.temporal_snapshot,
    )

    return {
        "session_id": session.id,
        "status": session.status,
        "date_from": request.date_from,
        "date_to": request.date_to,
        "temporal_snapshot": request.temporal_snapshot,
    }


@router.post("/temporal/compare")
async def compare_time_periods(
    request: TemporalComparisonRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser,
):
    """
    Compare search results across multiple time periods.

    Args:
        request: Temporal comparison parameters
        db: Database session
        current_user: Current user

    Returns:
        Comparison analysis
    """
    temporal_service = TemporalSearchService(db, current_user)

    results = await temporal_service.compare_time_periods(
        query_text=request.query,
        periods=request.periods,
        search_engine=request.search_engine,
        max_results=request.max_results,
    )

    return results
