"""Celery tasks for web scraping operations."""
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from celery import chain, group
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.celery_app import celery_app
from backend.database import AsyncSessionLocal
from backend.models.scraping import ScrapingJob
from backend.models.search import SearchSession, SearchResult
from backend.models.website import Website, WebsiteContent
from backend.core.scrapers.playwright_scraper import PlaywrightScraper
from backend.utils.content_extraction import filter_same_domain, filter_by_tlds

logger = logging.getLogger(__name__)


async def get_async_session() -> AsyncSession:
    """
    Get async database session for Celery tasks.

    Returns:
        AsyncSession instance
    """
    return AsyncSessionLocal()


@celery_app.task(bind=True, name="scrape_session", max_retries=0)
def scrape_session_task(self, job_id: int) -> dict:
    """
    Main task to orchestrate scraping for a search session.

    This task coordinates the entire scraping process:
    1. Loads job configuration
    2. Gets initial URLs from search results
    3. Chains tasks for each depth level

    Args:
        job_id: ScrapingJob ID

    Returns:
        Dict with status and results
    """
    import asyncio

    async def run_scraping():
        async with AsyncSessionLocal() as session:
            try:
                # Load scraping job
                result = await session.execute(
                    select(ScrapingJob).where(ScrapingJob.id == job_id)
                )
                job = result.scalar_one_or_none()

                if not job:
                    logger.error(f"ScrapingJob {job_id} not found")
                    return {"status": "failed", "error": "Job not found"}

                # Update job status
                job.status = "processing"
                job.started_at = datetime.utcnow()
                job.celery_task_id = self.request.id
                await session.commit()

                # Get initial URLs from search session
                result = await session.execute(
                    select(SearchResult)
                    .where(SearchResult.query_id.in_(
                        select(SearchResult.query_id)
                        .join(SearchResult.query)
                        .where(SearchResult.query.has(session_id=job.session_id))
                    ))
                    .order_by(SearchResult.rank)
                )
                search_results = result.scalars().all()

                if not search_results:
                    job.status = "completed"
                    job.completed_at = datetime.utcnow()
                    job.error_message = "No URLs to scrape"
                    await session.commit()
                    return {"status": "completed", "message": "No URLs to scrape"}

                # Get unique URLs
                initial_urls = list(set([r.url for r in search_results]))
                job.total_urls = len(initial_urls)
                await session.commit()

                logger.info(f"Starting scraping job {job_id} with {len(initial_urls)} initial URLs")

                # Scrape depth 1 (initial URLs)
                scraped_urls = set()
                next_level_urls = []

                for url in initial_urls:
                    result = await scrape_url_async(
                        job_id=job_id,
                        url=url,
                        depth=1,
                        parent_url=None,
                        session=session,
                    )

                    if result["status"] == "success":
                        scraped_urls.add(url)
                        if job.depth > 1 and result.get("outbound_links"):
                            next_level_urls.extend(result["outbound_links"])

                # Update progress
                job.urls_scraped = len(scraped_urls)
                job.current_depth = 1
                await session.commit()

                # Continue with depth 2 if configured
                if job.depth >= 2 and next_level_urls:
                    # Filter URLs based on domain filter settings
                    filtered_urls = await filter_urls(
                        urls=next_level_urls,
                        job=job,
                        already_scraped=scraped_urls,
                    )

                    logger.info(f"Scraping depth 2: {len(filtered_urls)} URLs")

                    # Update total URL count
                    job.total_urls += len(filtered_urls)
                    await session.commit()

                    depth2_results = []
                    for url in filtered_urls:
                        result = await scrape_url_async(
                            job_id=job_id,
                            url=url,
                            depth=2,
                            parent_url=None,  # Could track parent URL if needed
                            session=session,
                        )
                        depth2_results.append(result)

                        if result["status"] == "success":
                            scraped_urls.add(url)

                            if job.depth > 2 and result.get("outbound_links"):
                                next_level_urls.extend(result["outbound_links"])

                    # Update progress
                    job.urls_scraped = len(scraped_urls)
                    job.current_depth = 2
                    await session.commit()

                # Continue with depth 3 if configured
                if job.depth >= 3 and next_level_urls:
                    filtered_urls = await filter_urls(
                        urls=next_level_urls,
                        job=job,
                        already_scraped=scraped_urls,
                    )

                    logger.info(f"Scraping depth 3: {len(filtered_urls)} URLs")

                    job.total_urls += len(filtered_urls)
                    await session.commit()

                    for url in filtered_urls:
                        result = await scrape_url_async(
                            job_id=job_id,
                            url=url,
                            depth=3,
                            parent_url=None,
                            session=session,
                        )

                        if result["status"] == "success":
                            scraped_urls.add(url)

                    job.urls_scraped = len(scraped_urls)
                    job.current_depth = 3
                    await session.commit()

                # Mark job as completed
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                await session.commit()

                logger.info(f"Completed scraping job {job_id}: scraped {job.urls_scraped}/{job.total_urls} URLs")

                return {
                    "status": "completed",
                    "urls_scraped": job.urls_scraped,
                    "urls_failed": job.urls_failed,
                    "urls_skipped": job.urls_skipped,
                    "total_urls": job.total_urls,
                }

            except Exception as e:
                logger.error(f"Error in scraping job {job_id}: {e}", exc_info=True)

                # Update job status
                try:
                    result = await session.execute(
                        select(ScrapingJob).where(ScrapingJob.id == job_id)
                    )
                    job = result.scalar_one_or_none()
                    if job:
                        job.status = "failed"
                        job.completed_at = datetime.utcnow()
                        job.error_message = str(e)
                        job.error_count += 1
                        await session.commit()
                except Exception as update_error:
                    logger.error(f"Error updating job status: {update_error}")

                return {"status": "failed", "error": str(e)}

    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_scraping())
    finally:
        loop.close()


async def scrape_url_async(
    job_id: int,
    url: str,
    depth: int,
    parent_url: Optional[str],
    session: AsyncSession,
) -> dict:
    """
    Scrape a single URL asynchronously.

    Args:
        job_id: ScrapingJob ID
        url: URL to scrape
        depth: Current depth level
        parent_url: Parent URL that linked to this one
        session: Database session

    Returns:
        Dict with scraping result
    """
    try:
        # Load job configuration
        result = await session.execute(
            select(ScrapingJob).where(ScrapingJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            return {"status": "failed", "error": "Job not found"}

        # Check if domain is excluded
        if job.excluded_domains:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc

            # Check if domain or any parent domain is excluded
            for excluded in job.excluded_domains:
                excluded = excluded.lower().strip()
                if domain.lower() == excluded or domain.lower().endswith('.' + excluded):
                    logger.info(f"Skipping URL {url} - domain {domain} is in excluded list")
                    job.urls_skipped += 1
                    await session.commit()
                    return {"status": "skipped", "reason": "excluded_domain"}

        # Check if URL already scraped in this job
        existing = await session.execute(
            select(WebsiteContent)
            .where(
                WebsiteContent.scraping_job_id == job_id,
                WebsiteContent.url == url,
            )
        )
        if existing.scalar_one_or_none():
            logger.debug(f"URL {url} already scraped in this job")
            job.urls_skipped += 1
            await session.commit()
            return {"status": "skipped", "reason": "already_scraped"}

        # Create scraper
        scraper = PlaywrightScraper(
            delay_min=job.delay_min,
            delay_max=job.delay_max,
            max_retries=job.max_retries,
            timeout=job.timeout,
            respect_robots_txt=job.respect_robots_txt,
            headless=False,  # Run with visible browser (requires xvfb-run on server)
        )

        # Scrape URL
        scrape_result = await scraper.scrape(url)

        # Close scraper
        await scraper.close()

        # Get or create Website record
        domain = urlparse(url).netloc
        website_result = await session.execute(
            select(Website).where(Website.url == url)
        )
        website = website_result.scalar_one_or_none()

        if not website:
            website = Website(
                url=url,
                domain=domain,
                title=scrape_result.title,
                meta_description=scrape_result.meta_description,
            )
            session.add(website)
            await session.flush()

        # Update website metadata
        website.last_scraped_at = datetime.utcnow()
        website.scrape_count += 1
        if scrape_result.title:
            website.title = scrape_result.title
        if scrape_result.meta_description:
            website.meta_description = scrape_result.meta_description

        # Create WebsiteContent record
        content = WebsiteContent(
            website_id=website.id,
            user_id=job.user_id,
            scraping_job_id=job.id,
            url=url,
            html_content=scrape_result.html_content,
            extracted_text=scrape_result.extracted_text,
            title=scrape_result.title,
            meta_description=scrape_result.meta_description,
            language=scrape_result.language,
            word_count=scrape_result.word_count,
            scrape_depth=depth,
            parent_url=parent_url,
            status=scrape_result.status,
            error_message=scrape_result.error_message,
            outbound_links=scrape_result.outbound_links,
            http_status_code=scrape_result.http_status_code,
            final_url=scrape_result.final_url,
            scrape_duration=int(scrape_result.duration * 1000),  # Convert to milliseconds
        )
        session.add(content)

        # Update job statistics
        if scrape_result.status == "success":
            job.urls_scraped += 1
        elif scrape_result.status == "failed":
            job.urls_failed += 1
        elif scrape_result.status == "skipped":
            job.urls_skipped += 1

        await session.commit()

        logger.info(f"Scraped {url} (depth {depth}): {scrape_result.status}")

        return {
            "status": scrape_result.status,
            "url": url,
            "depth": depth,
            "outbound_links": scrape_result.outbound_links,
            "error": scrape_result.error_message,
        }

    except Exception as e:
        logger.error(f"Error scraping URL {url}: {e}", exc_info=True)

        # Update job error count
        try:
            result = await session.execute(
                select(ScrapingJob).where(ScrapingJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            if job:
                job.urls_failed += 1
                job.error_count += 1
                await session.commit()
        except Exception:
            pass

        return {"status": "failed", "url": url, "error": str(e)}


async def filter_urls(
    urls: list[str],
    job: ScrapingJob,
    already_scraped: set[str],
) -> list[str]:
    """
    Filter URLs based on job configuration.

    Args:
        urls: List of URLs to filter
        job: ScrapingJob with filter configuration
        already_scraped: Set of already scraped URLs

    Returns:
        Filtered list of URLs
    """
    # Remove duplicates and already scraped URLs
    unique_urls = set(urls) - already_scraped

    # Apply domain filtering
    if job.domain_filter == "same_domain":
        # Get base domain from session (use first search result URL)
        # For now, filter by each URL's own domain
        filtered = list(unique_urls)

    elif job.domain_filter == "allow_tld_list" and job.allowed_tlds:
        filtered = filter_by_tlds(list(unique_urls), job.allowed_tlds)

    else:  # allow_all
        filtered = list(unique_urls)

    return filtered


@celery_app.task(bind=True, name="cancel_scraping_job", max_retries=0)
def cancel_scraping_job_task(self, job_id: int) -> dict:
    """
    Cancel a running scraping job.

    Args:
        job_id: ScrapingJob ID to cancel

    Returns:
        Dict with cancellation status
    """
    import asyncio

    async def cancel_job():
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(ScrapingJob).where(ScrapingJob.id == job_id)
                )
                job = result.scalar_one_or_none()

                if not job:
                    return {"status": "error", "message": "Job not found"}

                if job.status not in ["pending", "processing"]:
                    return {"status": "error", "message": f"Job is {job.status}, cannot cancel"}

                # Revoke Celery task if it's running
                if job.celery_task_id:
                    celery_app.control.revoke(job.celery_task_id, terminate=True)

                # Update job status
                job.status = "cancelled"
                job.completed_at = datetime.utcnow()
                await session.commit()

                return {"status": "success", "message": "Job cancelled"}

            except Exception as e:
                logger.error(f"Error cancelling job {job_id}: {e}")
                return {"status": "error", "message": str(e)}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(cancel_job())
    finally:
        loop.close()
