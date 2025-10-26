"""Database connection and session management."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from backend.config import settings

# Create async engine with psycopg
# Note: psycopg URL should use postgresql+psycopg:// scheme
database_url = str(settings.database_url)
if "postgresql://" in database_url and "+psycopg" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://")

engine = create_async_engine(
    database_url,
    echo=settings.database_echo,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=settings.database_pool_pre_ping,
    pool_recycle=settings.database_pool_recycle,
    # Performance optimizations
    pool_use_lifo=True,  # Use LIFO for better connection reuse
    connect_args={
        "server_settings": {
            "application_name": "issue_observatory",
        },
        "command_timeout": 60,
    },
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Create declarative base
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides database session.

    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
