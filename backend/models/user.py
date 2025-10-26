"""User model for authentication and authorization."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.search import SearchSession
    from backend.models.website import WebsiteContent
    from backend.models.network import NetworkExport
    from backend.models.scraping import ScrapingJob


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    search_sessions: Mapped[list["SearchSession"]] = relationship(
        "SearchSession", back_populates="user", cascade="all, delete-orphan"
    )
    website_contents: Mapped[list["WebsiteContent"]] = relationship(
        "WebsiteContent", back_populates="user", cascade="all, delete-orphan"
    )
    network_exports: Mapped[list["NetworkExport"]] = relationship(
        "NetworkExport", back_populates="user", cascade="all, delete-orphan"
    )
    scraping_jobs: Mapped[list["ScrapingJob"]] = relationship(
        "ScrapingJob", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of User."""
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
