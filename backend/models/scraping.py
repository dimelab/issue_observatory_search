"""Scraping job models for tracking web scraping operations."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.user import User
    from backend.models.search import SearchSession
    from backend.models.website import WebsiteContent


class ScrapingJob(Base):
    """Scraping job model - tracks web scraping operations for search sessions."""

    __tablename__ = "scraping_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # pending, processing, completed, failed, cancelled

    # Scraping configuration
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1, 2, or 3
    domain_filter: Mapped[str] = mapped_column(
        String(50), nullable=False, default="same_domain"
    )  # same_domain, allow_all, allow_tld_list
    allowed_tlds: Mapped[list | None] = mapped_column(JSON, nullable=True)  # e.g., [".org", ".edu"]
    delay_min: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)  # seconds
    delay_max: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)  # seconds
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=30)  # seconds
    respect_robots_txt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Progress tracking
    total_urls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    urls_scraped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    urls_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    urls_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # robots.txt blocked, etc.

    # Current depth being processed
    current_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Celery task information
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="scraping_jobs")
    session: Mapped["SearchSession"] = relationship("SearchSession", back_populates="scraping_jobs")
    website_contents: Mapped[list["WebsiteContent"]] = relationship(
        "WebsiteContent", back_populates="scraping_job"
    )

    def __repr__(self) -> str:
        """String representation of ScrapingJob."""
        return f"<ScrapingJob(id={self.id}, name='{self.name}', status='{self.status}', depth={self.depth})>"

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_urls == 0:
            return 0.0
        return (self.urls_scraped / self.total_urls) * 100.0

    @property
    def is_active(self) -> bool:
        """Check if job is currently active."""
        return self.status in ["pending", "processing"]

    @property
    def is_finished(self) -> bool:
        """Check if job is finished (completed, failed, or cancelled)."""
        return self.status in ["completed", "failed", "cancelled"]
