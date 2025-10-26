"""Search session, query, and result models."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.user import User
    from backend.models.scraping import ScrapingJob


class SearchSession(Base):
    """Search session model - groups related searches."""

    __tablename__ = "search_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="search_sessions")
    queries: Mapped[list["SearchQuery"]] = relationship(
        "SearchQuery", back_populates="session", cascade="all, delete-orphan"
    )
    scraping_jobs: Mapped[list["ScrapingJob"]] = relationship(
        "ScrapingJob", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of SearchSession."""
        return f"<SearchSession(id={self.id}, name='{self.name}', status='{self.status}')>"


class SearchQuery(Base):
    """Search query model - individual search within a session."""

    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query_text: Mapped[str] = mapped_column(String(500), nullable=False)
    search_engine: Mapped[str] = mapped_column(String(50), nullable=False)
    max_results: Mapped[int] = mapped_column(Integer, nullable=False)
    allowed_domains: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Phase 7: Advanced search features
    date_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    date_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    temporal_snapshot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    domain_whitelist: Mapped[list | None] = mapped_column(JSON, nullable=True)
    domain_blacklist: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tld_filter: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sphere_filter: Mapped[list | None] = mapped_column(JSON, nullable=True)
    framing_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    session: Mapped["SearchSession"] = relationship("SearchSession", back_populates="queries")
    results: Mapped[list["SearchResult"]] = relationship(
        "SearchResult", back_populates="query", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of SearchQuery."""
        return f"<SearchQuery(id={self.id}, query='{self.query_text}', status='{self.status}')>"


class SearchResult(Base):
    """Search result model - individual result from a search query."""

    __tablename__ = "search_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    query_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("search_queries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scraped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    query: Mapped["SearchQuery"] = relationship("SearchQuery", back_populates="results")

    def __repr__(self) -> str:
        """String representation of SearchResult."""
        return f"<SearchResult(id={self.id}, url='{self.url}', rank={self.rank})>"
