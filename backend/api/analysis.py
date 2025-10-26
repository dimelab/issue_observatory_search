"""Analysis API endpoints for content NLP processing."""
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.analysis import (
    AnalyzeContentRequest,
    AnalyzeBatchRequest,
    AnalyzeJobRequest,
    AnalysisResultResponse,
    AnalysisStatusResponse,
    NounsSummaryResponse,
    EntitiesSummaryResponse,
    JobAggregateResponse,
    BatchAnalysisResponse,
    AnalysisDeleteResponse,
)
from backend.services.analysis_service import AnalysisService
from backend.tasks.analysis_tasks import (
    analyze_content_task,
    analyze_batch_task,
    analyze_job_task,
)
from backend.utils.dependencies import CurrentUser
from backend.models.website import WebsiteContent
from backend.models.scraping import ScrapingJob
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/analyze", response_model=AnalysisResultResponse, status_code=status.HTTP_200_OK)
async def analyze_content(
    request: AnalyzeContentRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> AnalysisResultResponse:
    """
    Analyze a single website content.

    Performs NLP analysis including noun extraction and named entity recognition.
    Results are cached for faster subsequent access.

    Args:
        request: Analysis configuration
        db: Database session
        current_user: Current authenticated user
        background_tasks: Background task manager

    Returns:
        AnalysisResultResponse: Analysis results with nouns and entities
    """
    service = AnalysisService(db)

    # Verify content exists and belongs to user
    stmt = select(WebsiteContent).where(
        WebsiteContent.id == request.content_id,
        WebsiteContent.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {request.content_id} not found or access denied",
        )

    try:
        result = await service.analyze_content(
            content_id=request.content_id,
            extract_nouns=request.extract_nouns,
            extract_entities=request.extract_entities,
            max_nouns=request.max_nouns,
            min_frequency=request.min_frequency,
        )

        logger.info(
            f"User {current_user.id} analyzed content {request.content_id}"
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error analyzing content {request.content_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze content: {str(e)}",
        )


@router.post("/batch", response_model=BatchAnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze_batch(
    request: AnalyzeBatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    background: bool = Query(
        True, description="Process in background (Celery task)"
    ),
) -> BatchAnalysisResponse:
    """
    Analyze multiple contents in batch.

    Can process synchronously or in background using Celery.
    Batch processing is more efficient than analyzing individually.

    Args:
        request: Batch analysis configuration
        db: Database session
        current_user: Current authenticated user
        background: If True, process in Celery task

    Returns:
        BatchAnalysisResponse: Batch status information
    """
    service = AnalysisService(db)

    # Verify all contents exist and belong to user
    stmt = select(WebsiteContent).where(
        WebsiteContent.id.in_(request.content_ids),
        WebsiteContent.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    contents = list(result.scalars().all())

    if len(contents) != len(request.content_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Some contents not found or access denied",
        )

    try:
        if background:
            # Queue Celery task
            task = analyze_batch_task.delay(
                content_ids=request.content_ids,
                extract_nouns=request.extract_nouns,
                extract_entities=request.extract_entities,
                max_nouns=request.max_nouns,
                min_frequency=request.min_frequency,
            )

            logger.info(
                f"User {current_user.id} queued batch analysis: "
                f"{len(request.content_ids)} contents (task: {task.id})"
            )

            return BatchAnalysisResponse(
                total_contents=len(request.content_ids),
                started=len(request.content_ids),
                status="queued",
                message=f"Batch analysis queued (task ID: {task.id})",
            )

        else:
            # Process synchronously
            result = await service.analyze_batch(
                content_ids=request.content_ids,
                extract_nouns=request.extract_nouns,
                extract_entities=request.extract_entities,
                max_nouns=request.max_nouns,
                min_frequency=request.min_frequency,
            )

            logger.info(
                f"User {current_user.id} completed batch analysis: "
                f"{result['successful']} successful, {result['failed']} failed"
            )

            return BatchAnalysisResponse(
                total_contents=result["total_contents"],
                started=result["processed"],
                status="completed",
                message=f"Analyzed {result['successful']} contents successfully",
            )

    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze batch: {str(e)}",
        )


@router.post("/job/{job_id}", response_model=BatchAnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze_job(
    job_id: int,
    request: AnalyzeJobRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> BatchAnalysisResponse:
    """
    Analyze all content from a scraping job.

    Queues a Celery task to analyze all contents associated with
    a scraping job in batch.

    Args:
        job_id: Scraping job ID
        request: Analysis configuration
        db: Database session
        current_user: Current authenticated user

    Returns:
        BatchAnalysisResponse: Task queue information
    """
    # Verify job exists and belongs to user
    stmt = select(ScrapingJob).where(
        ScrapingJob.id == job_id,
        ScrapingJob.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scraping job {job_id} not found or access denied",
        )

    try:
        # Queue Celery task
        task = analyze_job_task.delay(
            job_id=job_id,
            extract_nouns=request.extract_nouns,
            extract_entities=request.extract_entities,
            max_nouns=request.max_nouns,
            min_frequency=request.min_frequency,
        )

        logger.info(
            f"User {current_user.id} queued job analysis for job {job_id} "
            f"(task: {task.id})"
        )

        return BatchAnalysisResponse(
            total_contents=0,  # Will be determined by task
            started=0,
            status="queued",
            message=f"Job analysis queued (task ID: {task.id})",
        )

    except Exception as e:
        logger.error(f"Error queuing job analysis for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue job analysis: {str(e)}",
        )


@router.get("/content/{content_id}", response_model=AnalysisResultResponse)
async def get_analysis(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> AnalysisResultResponse:
    """
    Get complete analysis results for a content.

    Returns both nouns and entities with metadata.

    Args:
        content_id: Website content ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        AnalysisResultResponse: Full analysis results
    """
    service = AnalysisService(db)

    # Verify content exists and belongs to user
    stmt = select(WebsiteContent).where(
        WebsiteContent.id == content_id,
        WebsiteContent.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found or access denied",
        )

    # Check if analysis exists
    status_result = await service.get_analysis_status(content_id)

    if not status_result or status_result.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis not found or not completed for content {content_id}",
        )

    try:
        # Get nouns and entities
        nouns_result = await service.get_nouns(content_id)
        entities_result = await service.get_entities(content_id)

        return AnalysisResultResponse(
            content_id=content_id,
            url=content.url,
            language=content.language,
            word_count=content.word_count,
            status=status_result.status,
            nouns=nouns_result.nouns,
            entities=entities_result.entities,
            analyzed_at=status_result.completed_at,
            processing_duration=status_result.processing_duration,
        )

    except Exception as e:
        logger.error(f"Error getting analysis for content {content_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analysis: {str(e)}",
        )


@router.get("/content/{content_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> AnalysisStatusResponse:
    """
    Get analysis status for a content.

    Returns metadata about the analysis without the full results.

    Args:
        content_id: Website content ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        AnalysisStatusResponse: Analysis status and metadata
    """
    service = AnalysisService(db)

    # Verify content exists and belongs to user
    stmt = select(WebsiteContent).where(
        WebsiteContent.id == content_id,
        WebsiteContent.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found or access denied",
        )

    status_result = await service.get_analysis_status(content_id)

    if not status_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis not found for content {content_id}",
        )

    return status_result


@router.get("/content/{content_id}/nouns", response_model=NounsSummaryResponse)
async def get_nouns(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit results"),
) -> NounsSummaryResponse:
    """
    Get extracted nouns for a content.

    Args:
        content_id: Website content ID
        db: Database session
        current_user: Current authenticated user
        limit: Optional limit on results

    Returns:
        NounsSummaryResponse: Extracted nouns
    """
    service = AnalysisService(db)

    # Verify content exists and belongs to user
    stmt = select(WebsiteContent).where(
        WebsiteContent.id == content_id,
        WebsiteContent.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found or access denied",
        )

    try:
        return await service.get_nouns(content_id, limit)

    except Exception as e:
        logger.error(f"Error getting nouns for content {content_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get nouns: {str(e)}",
        )


@router.get("/content/{content_id}/entities", response_model=EntitiesSummaryResponse)
async def get_entities(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    label: Optional[str] = Query(None, description="Filter by entity type"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit results"),
) -> EntitiesSummaryResponse:
    """
    Get extracted entities for a content.

    Args:
        content_id: Website content ID
        db: Database session
        current_user: Current authenticated user
        label: Optional entity type filter (PERSON, ORG, etc.)
        limit: Optional limit on results

    Returns:
        EntitiesSummaryResponse: Extracted entities
    """
    service = AnalysisService(db)

    # Verify content exists and belongs to user
    stmt = select(WebsiteContent).where(
        WebsiteContent.id == content_id,
        WebsiteContent.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found or access denied",
        )

    try:
        return await service.get_entities(content_id, label, limit)

    except Exception as e:
        logger.error(f"Error getting entities for content {content_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get entities: {str(e)}",
        )


@router.get("/job/{job_id}/aggregate", response_model=JobAggregateResponse)
async def get_job_aggregate(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    top_n: int = Query(50, ge=1, le=500, description="Top N items"),
) -> JobAggregateResponse:
    """
    Get aggregated analysis results for a scraping job.

    Returns top nouns and entities across all analyzed contents
    in the job, with frequency statistics.

    Args:
        job_id: Scraping job ID
        db: Database session
        current_user: Current authenticated user
        top_n: Number of top items to return

    Returns:
        JobAggregateResponse: Aggregated analysis results
    """
    service = AnalysisService(db)

    # Verify job exists and belongs to user
    stmt = select(ScrapingJob).where(
        ScrapingJob.id == job_id,
        ScrapingJob.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scraping job {job_id} not found or access denied",
        )

    try:
        return await service.get_job_aggregate(job_id, top_n)

    except Exception as e:
        logger.error(f"Error getting job aggregate for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job aggregate: {str(e)}",
        )


@router.delete("/content/{content_id}", response_model=AnalysisDeleteResponse)
async def delete_analysis(
    content_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
) -> AnalysisDeleteResponse:
    """
    Delete analysis results for a content.

    Removes all nouns, entities, and analysis metadata.
    The content itself is not deleted.

    Args:
        content_id: Website content ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        AnalysisDeleteResponse: Deletion status
    """
    service = AnalysisService(db)

    # Verify content exists and belongs to user
    stmt = select(WebsiteContent).where(
        WebsiteContent.id == content_id,
        WebsiteContent.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found or access denied",
        )

    try:
        deleted = await service.delete_analysis(content_id)

        if deleted:
            logger.info(
                f"User {current_user.id} deleted analysis for content {content_id}"
            )
            return AnalysisDeleteResponse(
                content_id=content_id,
                deleted=True,
                message="Analysis deleted successfully",
            )
        else:
            return AnalysisDeleteResponse(
                content_id=content_id,
                deleted=False,
                message="No analysis found to delete",
            )

    except Exception as e:
        logger.error(f"Error deleting analysis for content {content_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete analysis: {str(e)}",
        )
