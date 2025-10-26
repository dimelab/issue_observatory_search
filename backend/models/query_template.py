"""Query template models for formulation strategies."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.user import User
    from backend.models.search import SearchQuery


class QueryTemplate(Base):
    """
    Query template model.

    Stores reusable query templates with variables for different
    formulation strategies (framings, perspectives, etc.).
    Templates can be user-defined or system-provided.
    """

    __tablename__ = "query_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    framing_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en", index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    generated_queries: Mapped[list["QueryFromTemplate"]] = relationship(
        "QueryFromTemplate", back_populates="template", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of QueryTemplate."""
        return f"<QueryTemplate(id={self.id}, name='{self.name}', framing='{self.framing_type}')>"


class QueryFromTemplate(Base):
    """
    Query from template model.

    Links a search query to the template it was generated from,
    storing the variable substitutions used.
    """

    __tablename__ = "queries_from_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("query_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    search_query_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("search_queries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    substitutions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    template: Mapped["QueryTemplate"] = relationship("QueryTemplate", back_populates="generated_queries")
    search_query: Mapped["SearchQuery"] = relationship("SearchQuery")

    def __repr__(self) -> str:
        """String representation of QueryFromTemplate."""
        return f"<QueryFromTemplate(id={self.id}, template_id={self.template_id})>"
