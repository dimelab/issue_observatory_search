"""Scraping service for managing web scraping operations."""
import logging
from typing import Optional
from datetime import datetime
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.scraping import ScrapingJob
from backend.models.search import SearchSession
from backend.models.website import WebsiteContent
from backend.tasks.scraping_tasks import scrape_session_task, cancel_scraping_job_task

logger = logging.getLogger(__name__)


class ScrapingService:
    """
    Service for managing web scraping operations.

    Handles:
    - Creating scraping jobs
    - Starting scraping tasks
    - Tracking job progress
    - Managing job lifecycle
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize scraping service.

        Args:
            db: Database session
        """
        self.db = db

    async def create_scraping_job(
        self,
        user_id: int,
        session_id: int,
        name: str,
        depth: int = 1,
        domain_filter: str = "same_domain",
        allowed_tlds: Optional[list[str]] = None,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        max_retries: int = 3,
        timeout: int = 30,
        respect_robots_txt: bool = True,
    ) -> ScrapingJob:
        """
        Create a new scraping job.

        Args:
            user_id: User ID creating the job
            session_id: Search session ID to scrape
            name: Job name
            depth: Scraping depth (1-3)
            domain_filter: Domain filter type
            allowed_tlds: List of allowed TLDs (for allow_tld_list filter)
            delay_min: Minimum delay between requests
            delay_max: Maximum delay between requests
            max_retries: Maximum retry attempts
            timeout: Request timeout in seconds
            respect_robots_txt: Whether to respect robots.txt

        Returns:
            Created ScrapingJob

        Raises:
            ValueError: If session not found or invalid parameters
        """
        # Validate session exists and belongs to user
        result = await self.db.execute(
            select(SearchSession).where(
                and_(
                    SearchSession.id == session_id,
                    SearchSession.user_id == user_id,
                )
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError("Search session not found or access denied")

        # Validate depth
        if depth not in [1, 2, 3]:
            raise ValueError("Depth must be 1, 2, or 3")

        # Validate domain filter
        if domain_filter not in ["same_domain", "allow_all", "allow_tld_list"]:
            raise ValueError("Invalid domain_filter value")

        if domain_filter == "allow_tld_list" and not allowed_tlds:
            raise ValueError("allowed_tlds required for allow_tld_list filter")

        # Create job
        job = ScrapingJob(
            user_id=user_id,
            session_id=session_id,
            name=name,
            status="pending",
            depth=depth,
            domain_filter=domain_filter,
            allowed_tlds=allowed_tlds,
            delay_min=delay_min,
            delay_max=delay_max,
            max_retries=max_retries,
            timeout=timeout,
            respect_robots_txt=respect_robots_txt,
        )

        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        logger.info(f"Created scraping job {job.id} for session {session_id}")

        return job

    async def start_scraping_job(self, job_id: int, user_id: int) -> ScrapingJob:
        """
        Start a scraping job by dispatching Celery task.

        Args:
            job_id: ScrapingJob ID to start
            user_id: User ID (for authorization)

        Returns:
            Updated ScrapingJob

        Raises:
            ValueError: If job not found or already started
        """
        # Load job
        result = await self.db.execute(
            select(ScrapingJob).where(
                and_(
                    ScrapingJob.id == job_id,
                    ScrapingJob.user_id == user_id,
                )
            )
        )
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError("Scraping job not found or access denied")

        if job.status != "pending":
            raise ValueError(f"Job is {job.status}, cannot start")

        # Dispatch Celery task
        task = scrape_session_task.apply_async(
            args=[job_id],
            queue="scraping",
        )

        # Update job with task ID
        job.celery_task_id = task.id
        job.status = "processing"
        job.started_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(job)

        logger.info(f"Started scraping job {job_id} with task {task.id}")

        return job

    async def get_job(self, job_id: int, user_id: int) -> Optional[ScrapingJob]:
        """
        Get a scraping job by ID.

        Args:
            job_id: ScrapingJob ID
            user_id: User ID (for authorization)

        Returns:
            ScrapingJob or None if not found
        """
        result = await self.db.execute(
            select(ScrapingJob).where(
                and_(
                    ScrapingJob.id == job_id,
                    ScrapingJob.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        user_id: int,
        session_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ScrapingJob], int]:
        """
        List scraping jobs for a user.

        Args:
            user_id: User ID
            session_id: Optional filter by session
            status: Optional filter by status
            limit: Maximum number of jobs to return
            offset: Offset for pagination

        Returns:
            Tuple of (jobs, total_count)
        """
        # Build query
        query = select(ScrapingJob).where(ScrapingJob.user_id == user_id)

        if session_id:
            query = query.where(ScrapingJob.session_id == session_id)

        if status:
            query = query.where(ScrapingJob.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get jobs
        query = query.order_by(ScrapingJob.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        jobs = result.scalars().all()

        return list(jobs), total

    async def cancel_job(self, job_id: int, user_id: int) -> ScrapingJob:
        """
        Cancel a running scraping job.

        Args:
            job_id: ScrapingJob ID to cancel
            user_id: User ID (for authorization)

        Returns:
            Updated ScrapingJob

        Raises:
            ValueError: If job not found or cannot be cancelled
        """
        # Load job
        result = await self.db.execute(
            select(ScrapingJob).where(
                and_(
                    ScrapingJob.id == job_id,
                    ScrapingJob.user_id == user_id,
                )
            )
        )
        job = result.scalar_one_or_none()

        if not job:
            raise ValueError("Scraping job not found or access denied")

        if job.status not in ["pending", "processing"]:
            raise ValueError(f"Job is {job.status}, cannot cancel")

        # Dispatch cancellation task
        cancel_scraping_job_task.apply_async(
            args=[job_id],
            queue="scraping",
        )

        logger.info(f"Cancellation requested for job {job_id}")

        return job

    async def delete_job(self, job_id: int, user_id: int) -> bool:
        """
        Delete a scraping job and its content.

        Args:
            job_id: ScrapingJob ID to delete
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If job is still active
        """
        # Load job
        result = await self.db.execute(
            select(ScrapingJob).where(
                and_(
                    ScrapingJob.id == job_id,
                    ScrapingJob.user_id == user_id,
                )
            )
        )
        job = result.scalar_one_or_none()

        if not job:
            return False

        if job.status in ["pending", "processing"]:
            raise ValueError("Cannot delete active job. Cancel it first.")

        # Delete job (cascade will delete WebsiteContent records)
        await self.db.delete(job)
        await self.db.commit()

        logger.info(f"Deleted scraping job {job_id}")

        return True

    async def get_job_content(
        self,
        job_id: int,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[WebsiteContent], int]:
        """
        Get scraped content for a job.

        Args:
            job_id: ScrapingJob ID
            user_id: User ID (for authorization)
            limit: Maximum number of content records to return
            offset: Offset for pagination

        Returns:
            Tuple of (content_list, total_count)
        """
        # Verify job access
        job = await self.get_job(job_id, user_id)
        if not job:
            return [], 0

        # Get total count
        count_query = select(func.count()).where(
            WebsiteContent.scraping_job_id == job_id
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get content
        query = (
            select(WebsiteContent)
            .where(WebsiteContent.scraping_job_id == job_id)
            .order_by(WebsiteContent.scrape_depth, WebsiteContent.scraped_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        content = result.scalars().all()

        return list(content), total

    async def get_website_content(
        self,
        website_id: int,
        user_id: int,
    ) -> Optional[WebsiteContent]:
        """
        Get latest scraped content for a website.

        Args:
            website_id: Website ID
            user_id: User ID (for authorization)

        Returns:
            WebsiteContent or None
        """
        result = await self.db.execute(
            select(WebsiteContent)
            .where(
                and_(
                    WebsiteContent.id == website_id,
                    WebsiteContent.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_job_statistics(self, job_id: int, user_id: int) -> dict:
        """
        Get detailed statistics for a scraping job.

        Args:
            job_id: ScrapingJob ID
            user_id: User ID (for authorization)

        Returns:
            Dict with job statistics
        """
        job = await self.get_job(job_id, user_id)
        if not job:
            return {}

        # Get content statistics
        stats_query = select(
            func.count(WebsiteContent.id).label("total_content"),
            func.count().filter(WebsiteContent.status == "success").label("successful"),
            func.count().filter(WebsiteContent.status == "failed").label("failed"),
            func.count().filter(WebsiteContent.status == "skipped").label("skipped"),
            func.avg(WebsiteContent.word_count).label("avg_word_count"),
            func.sum(WebsiteContent.word_count).label("total_words"),
        ).where(WebsiteContent.scraping_job_id == job_id)

        result = await self.db.execute(stats_query)
        stats = result.one()

        # Get depth distribution
        depth_query = select(
            WebsiteContent.scrape_depth,
            func.count(WebsiteContent.id).label("count"),
        ).where(
            WebsiteContent.scraping_job_id == job_id
        ).group_by(
            WebsiteContent.scrape_depth
        )

        depth_result = await self.db.execute(depth_query)
        depth_distribution = {row[0]: row[1] for row in depth_result}

        # Get language distribution
        lang_query = select(
            WebsiteContent.language,
            func.count(WebsiteContent.id).label("count"),
        ).where(
            and_(
                WebsiteContent.scraping_job_id == job_id,
                WebsiteContent.language.isnot(None),
            )
        ).group_by(
            WebsiteContent.language
        )

        lang_result = await self.db.execute(lang_query)
        language_distribution = {row[0]: row[1] for row in lang_result}

        return {
            "job_id": job.id,
            "status": job.status,
            "total_urls": job.total_urls,
            "urls_scraped": job.urls_scraped,
            "urls_failed": job.urls_failed,
            "urls_skipped": job.urls_skipped,
            "current_depth": job.current_depth,
            "progress_percentage": job.progress_percentage,
            "total_content": stats.total_content or 0,
            "successful": stats.successful or 0,
            "failed": stats.failed or 0,
            "skipped": stats.skipped or 0,
            "avg_word_count": float(stats.avg_word_count) if stats.avg_word_count else 0.0,
            "total_words": stats.total_words or 0,
            "depth_distribution": depth_distribution,
            "language_distribution": language_distribution,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
