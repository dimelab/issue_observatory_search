"""API endpoints that return HTML partials for HTMX."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import User, SearchSession, SearchQuery, SearchResult, ScrapingJob
from backend.models.website import WebsiteContent
from backend.utils.dependencies import CurrentUser
from urllib.parse import urlparse
from backend.api.frontend import format_datetime, format_number

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

# Register custom filters
templates.env.filters["format_datetime"] = format_datetime
templates.env.filters["format_number"] = format_number


@router.get("/api/search/sessions", response_class=HTMLResponse)
async def get_sessions_partial(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Get search sessions list as HTML partial."""
    # Calculate offset
    offset = (page - 1) * per_page

    # Get total count
    count_result = await db.execute(
        select(func.count(SearchSession.id)).where(SearchSession.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

    # Get sessions
    sessions_result = await db.execute(
        select(SearchSession)
        .where(SearchSession.user_id == current_user.id)
        .order_by(SearchSession.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    sessions = sessions_result.scalars().all()

    # Get additional data for each session
    sessions_data = []
    for session in sessions:
        # Get query count
        query_count_result = await db.execute(
            select(func.count(SearchQuery.id)).where(SearchQuery.session_id == session.id)
        )
        query_count = query_count_result.scalar() or 0

        # Get result count
        result_count_result = await db.execute(
            select(func.count(SearchResult.id))
            .join(SearchQuery)
            .where(SearchQuery.session_id == session.id)
        )
        result_count = result_count_result.scalar() or 0

        # Get unique domains
        unique_domains_result = await db.execute(
            select(func.count(func.distinct(SearchResult.domain)))
            .join(SearchQuery)
            .where(SearchQuery.session_id == session.id)
        )
        unique_domains = unique_domains_result.scalar() or 0

        sessions_data.append({
            "id": session.id,
            "name": session.name,
            "status": session.status or "completed",
            "search_engine": session.search_engine,
            "created_at": session.created_at,
            "query_count": query_count,
            "result_count": result_count,
            "unique_domains": unique_domains,
        })

    has_more = (offset + per_page) < total

    return templates.TemplateResponse(
        "partials/sessions_list.html",
        {
            "sessions": sessions_data,
            "has_more": has_more,
            "next_page": page + 1,
        }
    )


@router.get("/api/search/queries/{query_id}/results", response_class=HTMLResponse)
async def get_query_results_partial(
    request: Request,
    query_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get search results for a query as HTML partial."""
    # Verify query belongs to user
    query_result = await db.execute(
        select(SearchQuery)
        .join(SearchSession)
        .where(
            SearchQuery.id == query_id,
            SearchSession.user_id == current_user.id
        )
    )
    query = query_result.scalar_one_or_none()

    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found"
        )

    # Get results for this query
    results_result = await db.execute(
        select(SearchResult)
        .where(SearchResult.query_id == query_id)
        .order_by(SearchResult.rank)
    )
    results = results_result.scalars().all()

    results_data = []
    for result in results:
        results_data.append({
            "id": result.id,
            "title": result.title,
            "url": result.url,
            "description": result.description,
            "domain": result.domain,
            "position": result.rank,
            "is_scraped": result.scraped is not None,
        })

    return templates.TemplateResponse(
        "partials/query_results.html",
        {
            "request": request,
            "results": results_data,
        }
    )


@router.get("/api/scraping/jobs", response_class=HTMLResponse)
async def get_jobs_partial(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Get scraping jobs list as HTML partial."""
    # Build query
    query = select(ScrapingJob).where(ScrapingJob.user_id == current_user.id)

    if status_filter:
        query = query.where(ScrapingJob.status == status_filter)

    query = query.order_by(ScrapingJob.created_at.desc())

    # Get jobs
    jobs_result = await db.execute(query)
    jobs = jobs_result.scalars().all()

    # Get additional data for each job
    jobs_data = []
    for job in jobs:
        # Get session if exists
        session_data = None
        if job.session_id:
            session_result = await db.execute(
                select(SearchSession).where(SearchSession.id == job.session_id)
            )
            session = session_result.scalar_one_or_none()
            if session:
                session_data = {
                    "id": session.id,
                    "name": session.name,
                }

        # Get scraped content count
        scraped_count_result = await db.execute(
            select(func.count(WebsiteContent.id)).where(WebsiteContent.scraping_job_id == job.id)
        )
        scraped_count = scraped_count_result.scalar() or 0

        # Get success count
        success_count_result = await db.execute(
            select(func.count(WebsiteContent.id))
            .where(
                WebsiteContent.scraping_job_id == job.id,
                WebsiteContent.status == "success"
            )
        )
        success_count = success_count_result.scalar() or 0

        # Get failed count
        failed_count_result = await db.execute(
            select(func.count(WebsiteContent.id))
            .where(
                WebsiteContent.scraping_job_id == job.id,
                WebsiteContent.status == "failed"
            )
        )
        failed_count = failed_count_result.scalar() or 0

        jobs_data.append({
            "id": job.id,
            "name": job.name,
            "status": job.status or "pending",
            "depth": job.depth,
            "total_urls": job.total_urls or 0,
            "scraped_count": scraped_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "session": session_data,
        })

    return templates.TemplateResponse(
        "partials/jobs_list.html",
        {
            "jobs": jobs_data,
        }
    )


@router.get("/api/scraping/jobs/{job_id}/content", response_class=HTMLResponse)
async def get_job_content_partial(
    job_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """Get scraped content for a job as HTML partial."""
    # Verify job belongs to user
    job_result = await db.execute(
        select(ScrapingJob).where(
            ScrapingJob.id == job_id,
            ScrapingJob.user_id == current_user.id
        )
    )
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping job not found"
        )

    # Calculate offset
    offset = (page - 1) * per_page

    # Get total count
    count_result = await db.execute(
        select(func.count(WebsiteContent.id)).where(WebsiteContent.scraping_job_id == job_id)
    )
    total = count_result.scalar() or 0

    # Get scraped content
    content_result = await db.execute(
        select(WebsiteContent)
        .where(WebsiteContent.scraping_job_id == job_id)
        .order_by(WebsiteContent.scraped_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    content = content_result.scalars().all()

    content_data = []
    for item in content:
        content_data.append({
            "id": item.id,
            "url": item.url,
            "title": item.title,
            "domain": urlparse(item.url).netloc,
            "status": item.status,
            "word_count": item.word_count,
            "language": item.language,
            "description": item.meta_description,
            "scraped_at": item.scraped_at,
            "error_message": item.error_message,
        })

    has_more = (offset + per_page) < total

    return templates.TemplateResponse(
        "partials/scraped_content.html",
        {
            "content": content_data,
            "has_more": has_more,
            "next_page": page + 1,
            "job_id": job_id,
            "job_status": job.status,
        }
    )
