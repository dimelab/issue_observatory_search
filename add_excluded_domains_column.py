#!/usr/bin/env python3
"""Add excluded_domains column to scraping_jobs table."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from backend.database import AsyncSessionLocal


async def add_column():
    """Add excluded_domains column to scraping_jobs table."""
    async with AsyncSessionLocal() as session:
        try:
            # Check if column already exists
            check_sql = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='scraping_jobs'
                AND column_name='excluded_domains';
            """
            result = await session.execute(text(check_sql))
            exists = result.scalar_one_or_none()

            if exists:
                print("✅ Column 'excluded_domains' already exists")
                return

            # Add the column
            add_column_sql = """
                ALTER TABLE scraping_jobs
                ADD COLUMN excluded_domains JSON;
            """
            await session.execute(text(add_column_sql))
            await session.commit()

            print("✅ Successfully added 'excluded_domains' column to scraping_jobs table")

        except Exception as e:
            await session.rollback()
            print(f"❌ Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(add_column())
