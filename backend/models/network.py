"""Network export models for Phase 6."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON, Float, ARRAY, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.user import User


class NetworkExport(Base):
    """
    Network export model - generated network graphs.

    Stores metadata about generated network graphs including node/edge counts,
    backboning statistics, and file storage information.
    """

    __tablename__ = "network_exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # search_website, website_noun, website_concept

    # Source sessions
    session_ids: Mapped[list] = mapped_column(
        ARRAY(Integer), nullable=False, index=True
    )  # Array of session IDs

    # File storage
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # Bytes

    # Graph statistics
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Backboning information
    backboning_applied: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    backboning_algorithm: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # disparity_filter, etc.
    backboning_alpha: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_edge_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Before backboning
    backboning_statistics: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Additional stats

    # Network-specific metadata
    metadata: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # Languages, top_n, etc.

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="network_exports")

    def __repr__(self) -> str:
        """String representation of NetworkExport."""
        return (
            f"<NetworkExport(id={self.id}, name='{self.name}', "
            f"type='{self.type}', nodes={self.node_count}, edges={self.edge_count})>"
        )
