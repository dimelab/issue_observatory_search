"""Search API endpoints."""
import logging
import math
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.search import SearchSession, SearchQuery
from backend.schemas.search import (
    SearchAddQueriesRequest,
    SearchAddQueriesResponse,
    SearchExecuteRequest,
    SearchExecuteResponse,
    SearchProgressResponse,
    SearchRunPendingResponse,
    SearchSessionResponse,
    SearchSessionDetailResponse,
    SearchSessionListResponse,
    SearchQueryResponse,
    SearchResultResponse,
)
from backend.services.search_service import SearchQueueError, SearchService
from backend.utils.dependencies import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/execute", response_model=SearchExecuteResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_search(
    request: SearchExecuteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> SearchExecuteResponse:
    """
    Queue web searches for multiple keywords.

    Creates a search session with the keywords and hands the searching to a
    search worker, so this returns at once: follow the search with
    GET /session/{id}/progress. Results are deduplicated across keywords within
    the session.

    Args:
        request: Search execution request
        db: Database session
        current_user: Current authenticated user

    Returns:
        SearchExecuteResponse: Session id, the task id and status "pending"
            (queued)

    Raises:
        HTTPException: 400 if the search engine is not configured, 503 if the
            queue is not available
    """
    service = SearchService(db, current_user)

    try:
        # A missing API key is reported now, not from a worker
        service.ensure_engine_configured(request.search_engine)

        session, count = await service.queue_session(
            name=request.session_name,
            queries=request.queries,
            config={
                "search_engine": request.search_engine,
                "max_results": request.max_results,
                "language": request.language,
                "country": request.country,
                "allowed_domains": request.allowed_domains,
            }
        )
        task_id = await service.start(session)

        return SearchExecuteResponse(
            session_id=session.id,
            task_id=task_id,
            status=session.status,
            message=f"Search queued with {count} keywords",
            status_url=f"/api/search/session/{session.id}"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except SearchQueueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Failed to queue search")
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

        # Count scraped content from scraping jobs
        from backend.models.scraping import ScrapingJob
        from backend.models.website import WebsiteContent

        scraped_count_result = await db.execute(
            select(func.count(WebsiteContent.id))
            .join(ScrapingJob, WebsiteContent.scraping_job_id == ScrapingJob.id)
            .where(
                ScrapingJob.session_id == session.id,
                WebsiteContent.status == 'success'
            )
        )
        scraped_count = scraped_count_result.scalar() or 0

        # Count analyzed content
        from backend.models.analysis import ExtractedNoun

        analyzed_count_result = await db.execute(
            select(func.count(func.distinct(ExtractedNoun.website_content_id)))
            .join(WebsiteContent, ExtractedNoun.website_content_id == WebsiteContent.id)
            .join(ScrapingJob, WebsiteContent.scraping_job_id == ScrapingJob.id)
            .where(ScrapingJob.session_id == session.id)
        )
        analyzed_count = analyzed_count_result.scalar() or 0

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
                scraped_count=scraped_count,
                analyzed_count=analyzed_count,
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
        error_message=session.error_message,
        started_at=session.started_at,
        completed_at=session.completed_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
        queries=query_responses
    )


@router.post(
    "/session/{session_id}/queries",
    response_model=SearchAddQueriesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_session_queries(
    session_id: int,
    request: SearchAddQueriesRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> SearchAddQueriesResponse:
    """
    Add keywords to an existing search session.

    The keywords use the session's original search settings and are only
    queued (status "pending"); no search runs until
    POST /session/{session_id}/queries/run. Keywords already in the session
    are skipped and listed in the response.

    Args:
        session_id: Search session ID
        request: Keywords to add
        db: Database session
        current_user: Current authenticated user

    Returns:
        SearchAddQueriesResponse: Keywords added and skipped, and how many
            keywords are now waiting to be searched
    """
    service = SearchService(db, current_user)

    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search session not found"
        )

    added, skipped = await service.add_queries(session, request.queries)
    pending_count = await service.count_pending_queries(session.id)

    if added:
        message = f"Added {len(added)} keywords"
    else:
        message = "No new keywords: all were already in this session"

    return SearchAddQueriesResponse(
        session_id=session.id,
        added=[query.query_text for query in added],
        skipped=skipped,
        pending_count=pending_count,
        message=message,
    )


@router.post(
    "/session/{session_id}/queries/run",
    response_model=SearchRunPendingResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_session_queries(
    session_id: int,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> SearchRunPendingResponse:
    """
    Queue the search of the keywords added to a session and not yet collected.

    Also starts a search again after it failed or its worker was lost. The
    searching happens in a search worker: this returns at once, and the search
    is followed with GET /session/{id}/progress. Results are deduplicated
    against the session's existing results. With nothing to search it answers
    200 and queues nothing.

    Args:
        session_id: Search session ID
        response: Response, to set the status code
        db: Database session
        current_user: Current authenticated user

    Returns:
        SearchRunPendingResponse: The session status, task id and how many
            keywords were queued

    Raises:
        HTTPException: 404 if the session is not found, 409 if it is already
            being searched or waiting its turn, 400 if an engine is not
            configured, 503 if the queue is not available
    """
    service = SearchService(db, current_user)

    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search session not found"
        )

    if service.is_busy(session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This session is already being searched or waiting its turn"
        )

    queued = await service.count_unfinished_queries(session.id)
    if queued == 0:
        response.status_code = status.HTTP_200_OK
        return SearchRunPendingResponse(
            session_id=session.id,
            status=session.status,
            queued=0,
            message="No new keywords to search"
        )

    try:
        await service.ensure_engines_configured(session)
        # A person searching again starts the count of automatic restarts afresh
        if session.config and "auto_restarts" in session.config:
            session.config = {k: v for k, v in session.config.items() if k != "auto_restarts"}
        task_id = await service.start(session)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except SearchQueueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception:
        logger.exception(f"Failed to queue the search of session {session_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search for the new keywords"
        )

    return SearchRunPendingResponse(
        session_id=session.id,
        task_id=task_id,
        status=session.status,
        queued=queued,
        message=f"Search queued for {queued} keywords"
    )


@router.get("/session/{session_id}/progress", response_model=SearchProgressResponse)
async def get_session_progress(
    session_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> SearchProgressResponse:
    """
    How far a session's search has come.

    Cheap to call (counts only), meant for polling while a search runs. The
    session is "pending" while queued, "processing" while a worker searches it,
    then "completed" or "failed" (with error_message). "stale" means it says
    processing but the worker stopped reporting; searching again takes it over.

    Args:
        session_id: Session ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        SearchProgressResponse: Status and keyword counts

    Raises:
        HTTPException: 404 if the session is not found
    """
    service = SearchService(db, current_user)

    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search session not found"
        )

    return SearchProgressResponse(**await service.progress(session))


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

    session = await service.get_session(session_id)
    if session and service.is_busy(session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A search is still running for this session"
        )

    deleted = await service.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search session not found"
        )
