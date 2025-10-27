"""Frontend routes for serving HTML templates."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import User, SearchSession, SearchQuery, SearchResult, ScrapingJob
from backend.models.website import WebsiteContent
from backend.utils.dependencies import CurrentUser
from sqlalchemy import select, func

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


# Custom Jinja2 filters
def format_datetime(value: Optional[datetime]) -> str:
    """Format datetime for display."""
    if not value:
        return "N/A"

    now = datetime.utcnow()
    diff = now - value
    days = diff.days

    if days == 0:
        hours = diff.seconds // 3600
        if hours == 0:
            minutes = diff.seconds // 60
            if minutes == 0:
                return "Just now"
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif days == 1:
        return "Yesterday"
    elif days < 7:
        return f"{days} days ago"
    else:
        return value.strftime("%b %d, %Y at %I:%M %p")


def format_number(value: Optional[int]) -> str:
    """Format number with thousand separators."""
    if value is None:
        return "0"
    return f"{value:,}"


# Register custom filters
templates.env.filters["format_datetime"] = format_datetime
templates.env.filters["format_number"] = format_number


# Public routes (no authentication required)
@router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page."""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "show_nav": False,
            "show_footer": False,
        }
    )


# Protected routes (authentication required)
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Render dashboard page."""
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "show_nav": True,
            "show_footer": True,
            "active_page": "dashboard",
            "username": current_user.username,
        }
    )


@router.get("/search/new", response_class=HTMLResponse)
async def new_search(
    request: Request,
    current_user: CurrentUser,
):
    """Render new search page."""
    return templates.TemplateResponse(
        "search/new.html",
        {
            "request": request,
            "show_nav": True,
            "show_footer": True,
            "active_page": "search",
            "username": current_user.username,
        }
    )


@router.get("/search/session/{session_id}", response_class=HTMLResponse)
async def search_session(
    request: Request,
    session_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Render search session details page."""
    # Get session
    result = await db.execute(
        select(SearchSession).where(
            SearchSession.id == session_id,
            SearchSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search session not found"
        )

    # Get queries for this session
    queries_result = await db.execute(
        select(SearchQuery).where(SearchQuery.session_id == session_id)
    )
    queries = queries_result.scalars().all()

    # Get query count and result count
    query_count = len(queries)

    # Get result count
    result_count_result = await db.execute(
        select(func.count(SearchResult.id))
        .join(SearchQuery)
        .where(SearchQuery.session_id == session_id)
    )
    result_count = result_count_result.scalar() or 0

    # Get unique domains count
    unique_domains_result = await db.execute(
        select(func.count(func.distinct(SearchResult.domain)))
        .join(SearchQuery)
        .where(SearchQuery.session_id == session_id)
    )
    unique_domains = unique_domains_result.scalar() or 0

    # Prepare query data with result counts
    query_data = []
    for query in queries:
        query_result_count = await db.execute(
            select(func.count(SearchResult.id)).where(SearchResult.query_id == query.id)
        )
        count = query_result_count.scalar() or 0

        query_data.append({
            "id": query.id,
            "query_text": query.query_text,
            "status": query.status or "completed",
            "result_count": count,
        })

    return templates.TemplateResponse(
        "search/session.html",
        {
            "request": request,
            "show_nav": True,
            "show_footer": True,
            "active_page": "search",
            "username": current_user.username,
            "session": {
                "id": session.id,
                "name": session.name,
                "status": session.status or "completed",
                "search_engine": session.config.get("search_engine", "unknown") if session.config else "unknown",
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "query_count": query_count,
                "result_count": result_count,
                "unique_domains": unique_domains,
            },
            "queries": query_data,
        }
    )


@router.get("/scraping/jobs", response_class=HTMLResponse)
async def scraping_jobs(
    request: Request,
    current_user: CurrentUser,
):
    """Render scraping jobs page."""
    return templates.TemplateResponse(
        "scraping/jobs.html",
        {
            "request": request,
            "show_nav": True,
            "show_footer": True,
            "active_page": "scraping",
            "username": current_user.username,
        }
    )


@router.get("/scraping/job/{job_id}", response_class=HTMLResponse)
async def scraping_job(
    request: Request,
    job_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Render scraping job details page."""
    # Get job
    result = await db.execute(
        select(ScrapingJob).where(
            ScrapingJob.id == job_id,
            ScrapingJob.user_id == current_user.id
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping job not found"
        )

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
        select(func.count(WebsiteContent.id)).where(WebsiteContent.scraping_job_id == job_id)
    )
    scraped_count = scraped_count_result.scalar() or 0

    # Get success/failed counts
    success_count_result = await db.execute(
        select(func.count(WebsiteContent.id))
        .where(
            WebsiteContent.scraping_job_id == job_id,
            WebsiteContent.status == "success"
        )
    )
    success_count = success_count_result.scalar() or 0

    failed_count_result = await db.execute(
        select(func.count(WebsiteContent.id))
        .where(
            WebsiteContent.scraping_job_id == job_id,
            WebsiteContent.status == "failed"
        )
    )
    failed_count = failed_count_result.scalar() or 0

    return templates.TemplateResponse(
        "scraping/job.html",
        {
            "request": request,
            "show_nav": True,
            "show_footer": True,
            "active_page": "scraping",
            "username": current_user.username,
            "job": {
                "id": job.id,
                "name": job.name,
                "status": job.status or "pending",
                "depth": job.depth,
                "domain_filter": job.domain_filter,
                "delay_min": job.delay_min,
                "delay_max": job.delay_max,
                "respect_robots_txt": job.respect_robots_txt,
                "total_urls": job.total_urls or 0,
                "scraped_count": scraped_count,
                "success_count": success_count,
                "failed_count": failed_count,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "session": session_data,
            }
        }
    )


@router.get("/networks", response_class=HTMLResponse)
async def networks_list(
    request: Request,
    current_user: CurrentUser,
):
    """Render networks list page."""
    return templates.TemplateResponse(
        "networks/list.html",
        {
            "request": request,
            "show_nav": True,
            "show_footer": True,
            "active_page": "networks",
            "username": current_user.username,
        }
    )
