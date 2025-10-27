"""Search API endpoints."""
import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.search import SearchSession, SearchQuery
from backend.schemas.search import (
    SearchExecuteRequest,
    SearchExecuteResponse,
    SearchSessionResponse,
    SearchSessionDetailResponse,
    SearchSessionListResponse,
    SearchQueryResponse,
    SearchResultResponse,
)
from backend.services.search_service import SearchService
from backend.utils.dependencies import CurrentUser

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/execute", response_model=SearchExecuteResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_search(
    request: SearchExecuteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> SearchExecuteResponse:
    """
    Execute web searches for multiple keywords.

    Creates a search session and executes searches for all provided queries.
    Results are deduplicated across queries within the session.

    Args:
        request: Search execution request
        db: Database session
        current_user: Current authenticated user

    Returns:
        SearchExecuteResponse: Search session info and status
    """
    service = SearchService(db, current_user)

    try:
        # Create search session
        session = await service.create_session(
            name=request.session_name,
            config={
                "search_engine": request.search_engine,
                "max_results": request.max_results,
                "language": request.language,
                "country": request.country,
                "allowed_domains": request.allowed_domains,
                "auto_scrape": request.auto_scrape,
                "scrape_config": request.scrape_config.model_dump() if request.scrape_config else None,
            }
        )

        # Execute searches
        await service.execute_search(
            session=session,
            queries=request.queries,
            search_engine=request.search_engine,
            max_results=request.max_results,
            language=request.language,
            country=request.country,
            allowed_domains=request.allowed_domains
        )

        return SearchExecuteResponse(
            session_id=session.id,
            status=session.status,
            message=f"Search session created with {len(request.queries)} queries",
            status_url=f"/api/search/session/{session.id}"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute search: {str(e)}"
        )


@router.get("/sessions", response_model=SearchSessionListResponse)
async def list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
) -> SearchSessionListResponse:
    """
    Get all search sessions for current user.

    Args:
        db: Database session
        current_user: Current authenticated user
        page: Page number
        per_page: Results per page
        sort: Sort field
        order: Sort order

    Returns:
        SearchSessionListResponse: List of sessions with pagination
    """
    service = SearchService(db, current_user)

    skip = (page - 1) * per_page
    sessions, total = await service.list_sessions(
        skip=skip,
        limit=per_page,
        sort=sort,
        order=order
    )

    # Get query and website counts for each session
    session_responses = []
    for session in sessions:
        # Count queries
        query_count_result = await db.execute(
            select(func.count())
            .select_from(SearchQuery)
            .where(SearchQuery.session_id == session.id)
        )
        query_count = query_count_result.scalar() or 0

        # TODO: Count unique websites (Phase 3)
        website_count = 0

        session_responses.append(
            SearchSessionResponse(
                id=session.id,
                name=session.name,
                description=session.description,
                status=session.status,
                query_count=query_count,
                website_count=website_count,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
        )

    pages = math.ceil(total / per_page) if total > 0 else 0

    return SearchSessionListResponse(
        sessions=session_responses,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/session/{session_id}", response_model=SearchSessionDetailResponse)
async def get_session(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> SearchSessionDetailResponse:
    """
    Get detailed information about a search session.

    Args:
        session_id: Session ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        SearchSessionDetailResponse: Detailed session info

    Raises:
        HTTPException: If session not found
    """
    # Get session with queries and results
    result = await db.execute(
        select(SearchSession)
        .where(
            SearchSession.id == session_id,
            SearchSession.user_id == current_user.id
        )
        .options(
            selectinload(SearchSession.queries).selectinload(SearchQuery.results)
        )
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search session not found"
        )

    # Build query responses
    query_responses = []
    for query in session.queries:
        result_responses = [
            SearchResultResponse(
                id=r.id,
                url=r.url,
                title=r.title,
                description=r.description,
                rank=r.rank,
                domain=r.domain,
                scraped=r.scraped
            )
            for r in query.results
        ]

        query_responses.append(
            SearchQueryResponse(
                id=query.id,
                query_text=query.query_text,
                search_engine=query.search_engine,
                max_results=query.max_results,
                result_count=query.result_count,
                status=query.status,
                error_message=query.error_message,
                executed_at=query.executed_at,
                results=result_responses
            )
        )

    return SearchSessionDetailResponse(
        id=session.id,
        name=session.name,
        description=session.description,
        status=session.status,
        config=session.config,
        started_at=session.started_at,
        completed_at=session.completed_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
        queries=query_responses
    )


@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> None:
    """
    Delete a search session and all related data.

    Args:
        session_id: Session ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If session not found
    """
    service = SearchService(db, current_user)

    deleted = await service.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search session not found"
        )
