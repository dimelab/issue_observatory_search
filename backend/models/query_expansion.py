"""Query expansion models for snowballing."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.user import User
    from backend.models.search import SearchQuery, SearchSession


class QueryExpansionCandidate(Base):
    """
    Query expansion candidate model.

    Stores candidate terms generated through various expansion methods
    (search results analysis, content analysis, search suggestions).
    Candidates can be approved, rejected, or pending for user review.
    """

    __tablename__ = "query_expansion_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_query_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("search_queries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    candidate_term: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None, index=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    session: Mapped["SearchSession"] = relationship("SearchSession", foreign_keys=[session_id])
    parent_query: Mapped["SearchQuery"] = relationship("SearchQuery", foreign_keys=[parent_query_id])
    approved_by: Mapped["User"] = relationship("User", foreign_keys=[approved_by_user_id])

    def __repr__(self) -> str:
        """String representation of QueryExpansionCandidate."""
        return f"<QueryExpansionCandidate(id={self.id}, term='{self.candidate_term}', score={self.score})>"
