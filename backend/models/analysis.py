"""Analysis models for storing NLP processing results."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.website import WebsiteContent


class ExtractedNoun(Base):
    """
    Extracted nouns from website content with TF-IDF scoring.

    This table stores nouns extracted from text using spaCy NLP,
    ranked by TF-IDF importance scores.
    """

    __tablename__ = "extracted_nouns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    website_content_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("website_content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Noun information
    word: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # Original word form
    lemma: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # Lemmatized form
    frequency: Mapped[int] = mapped_column(Integer, nullable=False)  # Occurrence count
    tfidf_score: Mapped[float] = mapped_column(
        Float, nullable=False, index=True
    )  # TF-IDF score

    # Position data (stored as JSON array of integers)
    positions: Mapped[list] = mapped_column(JSON, nullable=False)

    # Language of the analysis
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # ISO 639-1 code

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    website_content: Mapped["WebsiteContent"] = relationship(
        "WebsiteContent", back_populates="extracted_nouns"
    )

    def __repr__(self) -> str:
        """String representation of ExtractedNoun."""
        return (
            f"<ExtractedNoun(id={self.id}, lemma='{self.lemma}', "
            f"freq={self.frequency}, tfidf={self.tfidf_score:.4f})>"
        )


class ExtractedEntity(Base):
    """
    Extracted named entities from website content.

    This table stores named entities (PERSON, ORG, GPE, etc.)
    extracted using spaCy's NER models.
    """

    __tablename__ = "extracted_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    website_content_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("website_content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Entity information
    text: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True
    )  # Entity text
    label: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # Entity type (PERSON, ORG, etc.)

    # Position in text
    start_pos: Mapped[int] = mapped_column(Integer, nullable=False)  # Character start
    end_pos: Mapped[int] = mapped_column(Integer, nullable=False)  # Character end

    # Optional confidence score
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Language of the analysis
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # ISO 639-1 code

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    website_content: Mapped["WebsiteContent"] = relationship(
        "WebsiteContent", back_populates="extracted_entities"
    )

    def __repr__(self) -> str:
        """String representation of ExtractedEntity."""
        return (
            f"<ExtractedEntity(id={self.id}, text='{self.text}', "
            f"label='{self.label}')>"
        )


class ContentAnalysis(Base):
    """
    Metadata about content analysis operations.

    This table tracks when content was analyzed, what options were used,
    and the status of the analysis.
    """

    __tablename__ = "content_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    website_content_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("website_content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,  # One analysis per content
    )

    # Analysis configuration
    extract_nouns: Mapped[bool] = mapped_column(Integer, default=True, nullable=False)
    extract_entities: Mapped[bool] = mapped_column(
        Integer, default=True, nullable=False
    )
    max_nouns: Mapped[int] = mapped_column(Integer, nullable=False)
    min_frequency: Mapped[int] = mapped_column(Integer, nullable=False)

    # Analysis results summary
    nouns_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    entities_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Analysis status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # pending, processing, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Processing time
    processing_duration: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # seconds

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
    website_content: Mapped["WebsiteContent"] = relationship(
        "WebsiteContent", back_populates="analysis"
    )

    def __repr__(self) -> str:
        """String representation of ContentAnalysis."""
        return (
            f"<ContentAnalysis(id={self.id}, content_id={self.website_content_id}, "
            f"status='{self.status}')>"
        )
