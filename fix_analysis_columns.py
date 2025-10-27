"""Fix content_analysis table column types."""
import asyncio
from sqlalchemy import text
from backend.database import AsyncSessionLocal


async def fix_columns():
    async with AsyncSessionLocal() as session:
        # Alter the columns to boolean type
        await session.execute(
            text("ALTER TABLE content_analysis ALTER COLUMN extract_nouns TYPE boolean USING extract_nouns::boolean")
        )
        await session.execute(
            text("ALTER TABLE content_analysis ALTER COLUMN extract_entities TYPE boolean USING extract_entities::boolean")
        )
        await session.commit()
        print("✓ Fixed content_analysis column types")


if __name__ == "__main__":
    asyncio.run(fix_columns())
