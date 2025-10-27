"""Debug script to check what data is available for network creation."""
import asyncio
from sqlalchemy import select, func
from backend.database import AsyncSessionLocal
from backend.models import SearchSession, ScrapingJob
from backend.models.website import WebsiteContent
from backend.models.analysis import ExtractedNoun, ExtractedEntity, ContentAnalysis


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

        # Check analysis data
        nouns = await db.execute(select(func.count(ExtractedNoun.id)))
        print(f'4. Extracted Nouns: {nouns.scalar()}')

        entities = await db.execute(select(func.count(ExtractedEntity.id)))
        print(f'5. Extracted Entities: {entities.scalar()}')

        analyses = await db.execute(select(func.count(ContentAnalysis.id)))
        print(f'6. Content Analyses: {analyses.scalar()}')

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

        # Check content with analysis
        print("\n" + "-" * 60)
        print("CONTENT WITH ANALYSIS:")
        print("-" * 60)
        result = await db.execute(
            select(WebsiteContent.id, WebsiteContent.url,
                   func.count(ExtractedNoun.id).label('noun_count'),
                   func.count(ExtractedEntity.id).label('entity_count'))
            .outerjoin(ExtractedNoun, WebsiteContent.id == ExtractedNoun.website_content_id)
            .outerjoin(ExtractedEntity, WebsiteContent.id == ExtractedEntity.website_content_id)
            .group_by(WebsiteContent.id, WebsiteContent.url)
            .having(func.count(ExtractedNoun.id) > 0)
            .limit(10)
        )
        content_with_analysis = result.all()
        if content_with_analysis:
            for row in content_with_analysis:
                print(f'  Content {row[0]}: {row[1][:60]}... (nouns: {row[2]}, entities: {row[3]})')
        else:
            print("  No analyzed content found")

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

        analyzed_content_result = await db.execute(
            select(func.count(func.distinct(ExtractedNoun.website_content_id)))
        )
        analyzed_count = analyzed_content_result.scalar()
        print(f"  ✓ Content with analysis: {analyzed_count}")

        print("\n" + "=" * 60)
        print("NEXT STEPS:")
        print("=" * 60)
        if analyzed_count == 0:
            print("⚠ No analyzed content found!")
            print("  You need to run analysis on your scraped content first.")
            print("  Look for an 'Analysis' menu or API endpoint to analyze content.")
        elif analyzed_count > 0:
            print("✓ You have analyzed content!")
            print("  You can now create networks from this data.")
            print("  Networks will show relationships between extracted nouns/entities.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(check_data())
