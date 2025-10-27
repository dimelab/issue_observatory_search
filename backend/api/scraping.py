"""API endpoints for web scraping operations."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.services.scraping_service import ScrapingService
from backend.schemas.scraping import (
    ScrapingJobCreate,
    ScrapingJobResponse,
    ScrapingJobList,
    ScrapingJobStatistics,
    WebsiteContentResponse,
    WebsiteContentList,
    ScrapingJobStatus,
    ScrapingError,
)
from backend.utils.dependencies import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraping", tags=["scraping"])


@router.post(
    "/jobs",
    response_model=ScrapingJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create scraping job",
    description="Create a new web scraping job for a search session",
)
async def create_scraping_job(
    job_data: ScrapingJobCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ScrapingJobResponse:
    """
    Create a new scraping job.

    Args:
        job_data: Scraping job configuration
        db: Database session
        current_user: Authenticated user

    Returns:
        Created scraping job

    Raises:
        HTTPException: If session not found or invalid parameters
    """
    try:
        service = ScrapingService(db)

        job = await service.create_scraping_job(
            user_id=current_user.id,
            session_id=job_data.session_id,
            name=job_data.name,
            depth=job_data.depth,
            domain_filter=job_data.domain_filter,
            allowed_tlds=job_data.allowed_tlds,
            delay_min=job_data.delay_min,
            delay_max=job_data.delay_max,
            max_retries=job_data.max_retries,
            timeout=job_data.timeout,
            respect_robots_txt=job_data.respect_robots_txt,
        )

        logger.info(f"User {current_user.id} created scraping job {job.id}")

        return ScrapingJobResponse.model_validate(job)

    except ValueError as e:
        logger.warning(f"Invalid scraping job creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error creating scraping job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create scraping job",
        )


@router.post(
    "/jobs/{job_id}/start",
    response_model=ScrapingJobResponse,
    summary="Start scraping job",
    description="Start a pending scraping job",
)
async def start_scraping_job(
    job_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ScrapingJobResponse:
    """
    Start a scraping job.

    Args:
        job_id: Scraping job ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated scraping job

    Raises:
        HTTPException: If job not found or cannot be started
    """
    try:
        service = ScrapingService(db)
        job = await service.start_scraping_job(job_id, current_user.id)

        logger.info(f"User {current_user.id} started scraping job {job_id}")

        return ScrapingJobResponse.model_validate(job)

    except ValueError as e:
        logger.warning(f"Cannot start scraping job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error starting scraping job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start scraping job",
        )


@router.get(
    "/jobs/{job_id}",
    response_model=ScrapingJobResponse,
    summary="Get scraping job",
    description="Get details of a scraping job",
)
async def get_scraping_job(
    job_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ScrapingJobResponse:
    """
    Get a scraping job by ID.

    Args:
        job_id: Scraping job ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Scraping job details

    Raises:
        HTTPException: If job not found
    """
    service = ScrapingService(db)
    job = await service.get_job(job_id, current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping job not found",
        )

    return ScrapingJobResponse.model_validate(job)


@router.get(
    "/jobs",
    response_model=ScrapingJobList,
    summary="List scraping jobs",
    description="List all scraping jobs for the current user",
)
async def list_scraping_jobs(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    session_id: Optional[int] = Query(None, description="Filter by session ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> ScrapingJobList:
    """
    List scraping jobs.

    Args:
        session_id: Optional filter by session
        status: Optional filter by status
        limit: Maximum results
        offset: Pagination offset
        db: Database session
        current_user: Authenticated user

    Returns:
        List of scraping jobs with pagination
    """
    service = ScrapingService(db)
    jobs, total = await service.list_jobs(
        user_id=current_user.id,
        session_id=session_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return ScrapingJobList(
        jobs=[ScrapingJobResponse.model_validate(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/jobs/{job_id}/statistics",
    response_model=ScrapingJobStatistics,
    summary="Get job statistics",
    description="Get detailed statistics for a scraping job",
)
async def get_job_statistics(
    job_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ScrapingJobStatistics:
    """
    Get job statistics.

    Args:
        job_id: Scraping job ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Job statistics

    Raises:
        HTTPException: If job not found
    """
    service = ScrapingService(db)
    stats = await service.get_job_statistics(job_id, current_user.id)

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scraping job not found",
        )

    return ScrapingJobStatistics(**stats)


@router.get(
    "/jobs/{job_id}/content",
    response_model=WebsiteContentList,
    summary="Get job content",
    description="Get scraped content for a job",
)
async def get_job_content(
    job_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> WebsiteContentList:
    """
    Get scraped content for a job.

    Args:
        job_id: Scraping job ID
        limit: Maximum results
        offset: Pagination offset
        db: Database session
        current_user: Authenticated user

    Returns:
        List of scraped content with pagination
    """
    service = ScrapingService(db)
    content, total = await service.get_job_content(
        job_id=job_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    return WebsiteContentList(
        content=[WebsiteContentResponse.model_validate(c) for c in content],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/content/{content_id}",
    response_model=WebsiteContentResponse,
    summary="Get website content",
    description="Get a specific scraped content record",
)
async def get_website_content(
    content_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> WebsiteContentResponse:
    """
    Get website content by ID.

    Args:
        content_id: Website content ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Website content details

    Raises:
        HTTPException: If content not found
    """
    service = ScrapingService(db)
    content = await service.get_website_content(content_id, current_user.id)

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website content not found",
        )

    return WebsiteContentResponse.model_validate(content)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=ScrapingJobStatus,
    summary="Cancel scraping job",
    description="Cancel a running scraping job",
)
async def cancel_scraping_job(
    job_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ScrapingJobStatus:
    """
    Cancel a scraping job.

    Args:
        job_id: Scraping job ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Cancellation status

    Raises:
        HTTPException: If job not found or cannot be cancelled
    """
    try:
        service = ScrapingService(db)
        await service.cancel_job(job_id, current_user.id)

        logger.info(f"User {current_user.id} cancelled scraping job {job_id}")

        return ScrapingJobStatus(
            status="success",
            message="Job cancellation requested",
        )

    except ValueError as e:
        logger.warning(f"Cannot cancel scraping job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error cancelling scraping job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel scraping job",
        )


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete scraping job",
    description="Delete a scraping job and its content",
)
async def delete_scraping_job(
    job_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a scraping job.

    Args:
        job_id: Scraping job ID
        db: Database session
        current_user: Authenticated user

    Raises:
        HTTPException: If job not found or cannot be deleted
    """
    try:
        service = ScrapingService(db)
        deleted = await service.delete_job(job_id, current_user.id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scraping job not found",
            )

        logger.info(f"User {current_user.id} deleted scraping job {job_id}")

    except ValueError as e:
        logger.warning(f"Cannot delete scraping job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error deleting scraping job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete scraping job",
        )
