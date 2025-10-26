"""Celery tasks for content analysis operations."""
import logging
from typing import Dict, Any, List
from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.celery_app import celery_app
from backend.config import settings
from backend.services.analysis_service import AnalysisService
from backend.models.website import WebsiteContent
from backend.models.scraping import ScrapingJob
from sqlalchemy import select

logger = logging.getLogger(__name__)


# Create async engine for Celery tasks
database_url = str(settings.database_url)
if "postgresql://" in database_url and "+psycopg" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://")

async_engine = create_async_engine(
    database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class AnalysisTask(Task):
    """Base task class for analysis operations with retry logic."""

    autoretry_for = (Exception,)
    max_retries = 3
    default_retry_delay = 60  # 1 minute
    retry_backoff = True  # Exponential backoff
    retry_backoff_max = 600  # Max 10 minutes
    retry_jitter = True  # Add randomness to prevent thundering herd


@celery_app.task(
    bind=True,
    base=AnalysisTask,
    name="backend.tasks.analysis_tasks.analyze_content_task",
    soft_time_limit=300,  # 5 minutes
    time_limit=600,  # 10 minutes
)
def analyze_content_task(
    self,
    content_id: int,
    extract_nouns: bool = True,
    extract_entities: bool = True,
    max_nouns: int = 100,
    min_frequency: int = 2,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Analyze a single content in background.

    This task runs the NLP analysis pipeline on a website content
    and stores the results in the database.

    Args:
        content_id: Website content ID
        extract_nouns: Whether to extract nouns
        extract_entities: Whether to extract entities
        max_nouns: Maximum nouns to extract
        min_frequency: Minimum noun frequency
        force_refresh: Skip cache and re-analyze

    Returns:
        Dictionary with analysis results
    """
    import asyncio

    logger.info(f"Starting analysis task for content_id={content_id}")

    # Update task state
    self.update_state(
        state="PROCESSING",
        meta={"content_id": content_id, "status": "analyzing"},
    )

    async def _run_analysis():
        """Run the analysis in async context."""
        async with AsyncSessionLocal() as session:
            try:
                service = AnalysisService(session)

                result = await service.analyze_content(
                    content_id=content_id,
                    extract_nouns=extract_nouns,
                    extract_entities=extract_entities,
                    max_nouns=max_nouns,
                    min_frequency=min_frequency,
                    force_refresh=force_refresh,
                )

                return {
                    "content_id": content_id,
                    "status": "completed",
                    "nouns_count": len(result.nouns),
                    "entities_count": len(result.entities),
                    "processing_duration": result.processing_duration,
                }

            except Exception as e:
                logger.error(f"Error in analysis task for content {content_id}: {e}")
                raise

    # Run async function in new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run_analysis())
        logger.info(
            f"Completed analysis task for content_id={content_id}: "
            f"{result['nouns_count']} nouns, {result['entities_count']} entities"
        )
        return result
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    base=AnalysisTask,
    name="backend.tasks.analysis_tasks.analyze_batch_task",
    soft_time_limit=1800,  # 30 minutes
    time_limit=3600,  # 1 hour
)
def analyze_batch_task(
    self,
    content_ids: List[int],
    extract_nouns: bool = True,
    extract_entities: bool = True,
    max_nouns: int = 100,
    min_frequency: int = 2,
) -> Dict[str, Any]:
    """
    Analyze multiple contents in background batch.

    This task processes multiple contents efficiently using
    the batch analyzer.

    Args:
        content_ids: List of content IDs
        extract_nouns: Whether to extract nouns
        extract_entities: Whether to extract entities
        max_nouns: Maximum nouns per document
        min_frequency: Minimum noun frequency

    Returns:
        Dictionary with batch statistics
    """
    import asyncio

    logger.info(f"Starting batch analysis task for {len(content_ids)} contents")

    # Update task state
    self.update_state(
        state="PROCESSING",
        meta={
            "total_contents": len(content_ids),
            "status": "analyzing",
        },
    )

    async def _run_batch_analysis():
        """Run the batch analysis in async context."""
        async with AsyncSessionLocal() as session:
            try:
                service = AnalysisService(session)

                result = await service.analyze_batch(
                    content_ids=content_ids,
                    extract_nouns=extract_nouns,
                    extract_entities=extract_entities,
                    max_nouns=max_nouns,
                    min_frequency=min_frequency,
                )

                return result

            except Exception as e:
                logger.error(f"Error in batch analysis task: {e}")
                raise

    # Run async function in new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run_batch_analysis())
        logger.info(
            f"Completed batch analysis task: {result['successful']} successful, "
            f"{result['failed']} failed in {result['processing_time']:.2f}s"
        )
        return result
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    base=AnalysisTask,
    name="backend.tasks.analysis_tasks.analyze_job_task",
    soft_time_limit=3600,  # 1 hour
    time_limit=7200,  # 2 hours
)
def analyze_job_task(
    self,
    job_id: int,
    extract_nouns: bool = True,
    extract_entities: bool = True,
    max_nouns: int = 100,
    min_frequency: int = 2,
) -> Dict[str, Any]:
    """
    Analyze all content from a scraping job.

    This task fetches all contents from a scraping job and
    analyzes them in batch.

    Args:
        job_id: Scraping job ID
        extract_nouns: Whether to extract nouns
        extract_entities: Whether to extract entities
        max_nouns: Maximum nouns per document
        min_frequency: Minimum noun frequency

    Returns:
        Dictionary with job analysis statistics
    """
    import asyncio

    logger.info(f"Starting job analysis task for job_id={job_id}")

    # Update task state
    self.update_state(
        state="PROCESSING",
        meta={"job_id": job_id, "status": "fetching contents"},
    )

    async def _run_job_analysis():
        """Run the job analysis in async context."""
        async with AsyncSessionLocal() as session:
            try:
                # Fetch job to verify it exists
                stmt = select(ScrapingJob).where(ScrapingJob.id == job_id)
                result = await session.execute(stmt)
                job = result.scalar_one_or_none()

                if not job:
                    raise ValueError(f"Scraping job {job_id} not found")

                # Fetch all content IDs for the job
                stmt = select(WebsiteContent.id).where(
                    WebsiteContent.scraping_job_id == job_id
                )
                result = await session.execute(stmt)
                content_ids = [row[0] for row in result.all()]

                if not content_ids:
                    logger.warning(f"No contents found for job {job_id}")
                    return {
                        "job_id": job_id,
                        "total_contents": 0,
                        "successful": 0,
                        "failed": 0,
                        "processing_time": 0,
                    }

                logger.info(
                    f"Found {len(content_ids)} contents for job {job_id}"
                )

                # Update task state
                self.update_state(
                    state="PROCESSING",
                    meta={
                        "job_id": job_id,
                        "total_contents": len(content_ids),
                        "status": "analyzing",
                    },
                )

                # Analyze all contents in batch
                service = AnalysisService(session)
                result = await service.analyze_batch(
                    content_ids=content_ids,
                    extract_nouns=extract_nouns,
                    extract_entities=extract_entities,
                    max_nouns=max_nouns,
                    min_frequency=min_frequency,
                )

                result["job_id"] = job_id
                return result

            except Exception as e:
                logger.error(f"Error in job analysis task for job {job_id}: {e}")
                raise

    # Run async function in new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run_job_analysis())
        logger.info(
            f"Completed job analysis task for job_id={job_id}: "
            f"{result['successful']} successful, {result['failed']} failed"
        )
        return result
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="backend.tasks.analysis_tasks.cleanup_old_analyses_task",
    soft_time_limit=600,  # 10 minutes
    time_limit=900,  # 15 minutes
)
def cleanup_old_analyses_task(self, days_old: int = 30) -> Dict[str, Any]:
    """
    Clean up old failed analysis records.

    This task removes analysis records that failed and are older
    than the specified number of days.

    Args:
        days_old: Number of days old for cleanup

    Returns:
        Dictionary with cleanup statistics
    """
    import asyncio
    from datetime import datetime, timedelta
    from sqlalchemy import delete
    from backend.models.analysis import ContentAnalysis

    logger.info(f"Starting cleanup of analyses older than {days_old} days")

    async def _run_cleanup():
        """Run the cleanup in async context."""
        async with AsyncSessionLocal() as session:
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=days_old)

                # Delete failed analyses older than cutoff
                stmt = delete(ContentAnalysis).where(
                    ContentAnalysis.status == "failed",
                    ContentAnalysis.created_at < cutoff_date,
                )

                result = await session.execute(stmt)
                await session.commit()

                deleted_count = result.rowcount

                logger.info(
                    f"Cleaned up {deleted_count} old failed analyses"
                )

                return {
                    "deleted_count": deleted_count,
                    "days_old": days_old,
                    "cutoff_date": cutoff_date.isoformat(),
                }

            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                raise

    # Run async function in new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run_cleanup())
        return result
    finally:
        loop.close()
