"""Website and content models for scraping operations."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.user import User
    from backend.models.scraping import ScrapingJob
    from backend.models.analysis import ExtractedNoun, ExtractedEntity, ContentAnalysis


class Website(Base):
    """Website model - unique websites discovered."""

    __tablename__ = "websites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scrape_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    contents: Mapped[list["WebsiteContent"]] = relationship(
        "WebsiteContent", back_populates="website", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of Website."""
        return f"<Website(id={self.id}, domain='{self.domain}')>"


class WebsiteContent(Base):
    """Scraped content from websites."""

    __tablename__ = "website_content"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    website_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scraping_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scraping_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Content fields
    html_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Language and statistics
    language: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Scraping metadata
    scrape_depth: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    parent_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # URL that linked to this page
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # success, failed, skipped
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Outbound links discovered on this page
    outbound_links: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # HTTP response information
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # After redirects

    # Timing
    scrape_duration: Mapped[float | None] = mapped_column(Integer, nullable=True)  # milliseconds
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    website: Mapped["Website"] = relationship("Website", back_populates="contents")
    user: Mapped["User"] = relationship("User", back_populates="website_contents")
    scraping_job: Mapped["ScrapingJob"] = relationship("ScrapingJob", back_populates="website_contents")
    extracted_nouns: Mapped[list["ExtractedNoun"]] = relationship(
        "ExtractedNoun", back_populates="website_content", cascade="all, delete-orphan"
    )
    extracted_entities: Mapped[list["ExtractedEntity"]] = relationship(
        "ExtractedEntity", back_populates="website_content", cascade="all, delete-orphan"
    )
    analysis: Mapped["ContentAnalysis"] = relationship(
        "ContentAnalysis", back_populates="website_content", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of WebsiteContent."""
        return f"<WebsiteContent(id={self.id}, website_id={self.website_id}, status='{self.status}')>"
