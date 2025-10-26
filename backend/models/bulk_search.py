"""Bulk search models for CSV upload."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.user import User
    from backend.models.search import SearchSession, SearchQuery


class BulkSearchUpload(Base):
    """
    Bulk search upload model.

    Stores metadata for CSV bulk search uploads, including
    validation status and execution results.
    """

    __tablename__ = "bulk_search_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    validation_errors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("search_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    session: Mapped["SearchSession"] = relationship("SearchSession")
    rows: Mapped[list["BulkSearchRow"]] = relationship(
        "BulkSearchRow", back_populates="upload", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of BulkSearchUpload."""
        return f"<BulkSearchUpload(id={self.id}, filename='{self.filename}', status='{self.validation_status}')>"


class BulkSearchRow(Base):
    """
    Bulk search row model.

    Stores individual rows from bulk search CSV,
    tracking execution status for each query.
    """

    __tablename__ = "bulk_search_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bulk_search_uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    query_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_query_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("search_queries.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    upload: Mapped["BulkSearchUpload"] = relationship("BulkSearchUpload", back_populates="rows")
    search_query: Mapped["SearchQuery"] = relationship("SearchQuery")

    def __repr__(self) -> str:
        """String representation of BulkSearchRow."""
        return f"<BulkSearchRow(id={self.id}, row={self.row_number}, status='{self.status}')>"
