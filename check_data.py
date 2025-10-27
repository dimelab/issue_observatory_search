"""Debug script to check what data is available for network creation."""
import asyncio
from sqlalchemy import select, func
from backend.database import AsyncSessionLocal
from backend.models import SearchSession, ScrapingJob
from backend.models.website import WebsiteContent
from backend.models.analysis import AnalysisJob


async def check_data():
    async with AsyncSessionLocal() as db:
        print("=" * 60)
        print("DATABASE DATA CHECK")
        print("=" * 60)

        # Check search sessions
        sessions = await db.execute(select(func.count(SearchSession.id)))
        print(f'\n1. Search Sessions: {sessions.scalar()}')

        # Check scraping jobs
        jobs = await db.execute(select(func.count(ScrapingJob.id)))
        print(f'2. Scraping Jobs: {jobs.scalar()}')

        # Check scraped content
        content = await db.execute(select(func.count(WebsiteContent.id)))
        print(f'3. Scraped Content: {content.scalar()}')

        # Check analysis jobs
        analysis = await db.execute(select(func.count(AnalysisJob.id)))
        print(f'4. Analysis Jobs: {analysis.scalar()}')

        # Check scraping jobs with content
        print("\n" + "-" * 60)
        print("SCRAPING JOBS DETAIL:")
        print("-" * 60)
        result = await db.execute(
            select(ScrapingJob.id, ScrapingJob.name, ScrapingJob.status, func.count(WebsiteContent.id))
            .outerjoin(WebsiteContent, ScrapingJob.id == WebsiteContent.scraping_job_id)
            .group_by(ScrapingJob.id, ScrapingJob.name, ScrapingJob.status)
            .order_by(ScrapingJob.id)
        )
        jobs_data = result.all()
        if jobs_data:
            for row in jobs_data:
                print(f'  Job {row[0]}: "{row[1]}" (status: {row[2]}, content items: {row[3]})')
        else:
            print("  No scraping jobs found")

        # Check analysis jobs detail
        print("\n" + "-" * 60)
        print("ANALYSIS JOBS DETAIL:")
        print("-" * 60)
        result = await db.execute(
            select(AnalysisJob.id, AnalysisJob.name, AnalysisJob.status, AnalysisJob.job_type)
            .order_by(AnalysisJob.id)
        )
        analysis_data = result.all()
        if analysis_data:
            for row in analysis_data:
                print(f'  Job {row[0]}: "{row[1]}" (status: {row[2]}, type: {row[3]})')
        else:
            print("  No analysis jobs found")

        # Check what's needed for network creation
        print("\n" + "=" * 60)
        print("NETWORK CREATION REQUIREMENTS:")
        print("=" * 60)
        print("To create networks, you need:")
        print("  1. Completed scraping jobs with content")
        print("  2. Run analysis on the scraped content")
        print("  3. Networks are created from analysis results")
        print("\nCurrent status:")

        completed_jobs = await db.execute(
            select(func.count(ScrapingJob.id))
            .where(ScrapingJob.status == 'completed')
        )
        print(f"  ✓ Completed scraping jobs: {completed_jobs.scalar()}")

        content_count = await db.execute(
            select(func.count(WebsiteContent.id))
            .where(WebsiteContent.status == 'success')
        )
        print(f"  ✓ Successfully scraped pages: {content_count.scalar()}")

        completed_analysis = await db.execute(
            select(func.count(AnalysisJob.id))
            .where(AnalysisJob.status == 'completed')
        )
        print(f"  ✓ Completed analysis jobs: {completed_analysis.scalar()}")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(check_data())
