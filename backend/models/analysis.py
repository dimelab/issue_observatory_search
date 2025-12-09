"""Analysis models for storing NLP processing results."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

if TYPE_CHECKING:
    from backend.models.website import WebsiteContent


class ExtractedNoun(Base):
    """
    Extracted keywords from website content (formerly nouns-only).

    Enhanced in v6.0.0 to support multiple extraction methods:
    - noun: Original spaCy noun extraction (backward compatible)
    - all_pos: Nouns, verbs, adjectives
    - tfidf: TF-IDF with bigrams
    - rake: RAKE algorithm with n-grams

    Note: Table name remains "extracted_nouns" for backward compatibility.
    The model now represents keywords more broadly.
    """

    __tablename__ = "extracted_nouns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    website_content_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("website_content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Keyword information
    word: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # Original word or phrase
    lemma: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # Lemmatized form
    frequency: Mapped[int] = mapped_column(Integer, nullable=False)  # Occurrence count
    tfidf_score: Mapped[float] = mapped_column(
        Float, nullable=False, index=True
    )  # TF-IDF or other importance score

    # Position data (stored as JSON array of integers)
    positions: Mapped[list] = mapped_column(JSON, nullable=False)

    # Language of the analysis
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # ISO 639-1 code

    # v6.0.0: New fields for enhanced extraction methods
    extraction_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="noun",
        index=True,
        comment="Extraction method: noun, all_pos, tfidf, rake"
    )

    phrase_length: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of words in keyword phrase (for n-grams)"
    )

    pos_tag: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Part of speech tag: NOUN, VERB, ADJ, etc."
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    website_content: Mapped["WebsiteContent"] = relationship(
        "WebsiteContent", back_populates="extracted_nouns"
    )

    def __repr__(self) -> str:
        """String representation of ExtractedNoun (Keyword)."""
        return (
            f"<ExtractedNoun(id={self.id}, lemma='{self.lemma}', "
            f"method='{self.extraction_method}', "
            f"freq={self.frequency}, score={self.tfidf_score:.4f})>"
        )


# Alias for backward compatibility and clarity
ExtractedKeyword = ExtractedNoun


class ExtractedEntity(Base):
    """
    Extracted named entities from website content.

    Enhanced in v6.0.0 to support:
    - spaCy NER (existing, fast)
    - Transformer-based NER (new, more accurate, multilingual)

    Stores named entities (PERSON, ORG, GPE, LOC, etc.)
    with confidence scores and extraction method metadata.
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
    )  # Entity type (PERSON, ORG, GPE, LOC, MISC, etc.)

    # Position in text
    start_pos: Mapped[int] = mapped_column(Integer, nullable=False)  # Character start
    end_pos: Mapped[int] = mapped_column(Integer, nullable=False)  # Character end

    # Confidence score (now required for v6.0.0)
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, index=True
    )  # 0.0-1.0

    # v6.0.0: Frequency tracking for aggregated entities
    frequency: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Number of times this entity appears in the text"
    )

    # Language of the analysis
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # ISO 639-1 code

    # v6.0.0: Extraction method tracking
    extraction_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="spacy",
        index=True,
        comment="Extraction method: spacy or transformer"
    )

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
            f"label='{self.label}', method='{self.extraction_method}', "
            f"confidence={self.confidence:.2f})>"
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
    extract_nouns: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extract_entities: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
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
