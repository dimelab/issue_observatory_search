"""Pydantic schemas for content analysis operations."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# Request Schemas


class AnalysisOptionsBase(BaseModel):
    """Base options for content analysis."""

    extract_nouns: bool = Field(
        default=True, description="Whether to extract nouns from text"
    )
    extract_entities: bool = Field(
        default=True, description="Whether to extract named entities from text"
    )
    max_nouns: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of nouns to extract per document",
    )
    min_frequency: int = Field(
        default=2,
        ge=1,
        le=100,
        description="Minimum frequency for a noun to be included",
    )


class AnalyzeContentRequest(AnalysisOptionsBase):
    """Request to analyze a single content."""

    content_id: int = Field(..., gt=0, description="Website content ID to analyze")


class AnalyzeBatchRequest(AnalysisOptionsBase):
    """Request to analyze multiple contents in batch."""

    content_ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="List of content IDs to analyze"
    )

    @field_validator("content_ids")
    @classmethod
    def validate_content_ids(cls, v: list[int]) -> list[int]:
        """Validate that all content IDs are positive and unique."""
        if not all(cid > 0 for cid in v):
            raise ValueError("All content IDs must be positive integers")
        if len(v) != len(set(v)):
            raise ValueError("Content IDs must be unique")
        return v


class AnalyzeJobRequest(AnalysisOptionsBase):
    """Request to analyze all content from a scraping job."""

    job_id: int = Field(..., gt=0, description="Scraping job ID to analyze")


# Response Schemas


class ExtractedNounResponse(BaseModel):
    """Response schema for extracted nouns."""

    word: str = Field(..., description="Original word form")
    lemma: str = Field(..., description="Lemmatized (base) form of the word")
    frequency: int = Field(..., description="Number of times word appears")
    tfidf_score: float = Field(..., description="TF-IDF importance score")
    positions: list[int] = Field(
        default_factory=list, description="Character positions in text"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True


class ExtractedEntityResponse(BaseModel):
    """Response schema for extracted named entities."""

    text: str = Field(..., description="Entity text")
    label: str = Field(..., description="Entity type (PERSON, ORG, GPE, etc.)")
    start_pos: int = Field(..., description="Character position where entity starts")
    end_pos: int = Field(..., description="Character position where entity ends")
    confidence: Optional[float] = Field(None, description="Optional confidence score")

    class Config:
        """Pydantic config."""

        from_attributes = True


class AnalysisStatusResponse(BaseModel):
    """Response schema for analysis status."""

    content_id: int = Field(..., description="Website content ID")
    status: str = Field(
        ..., description="Analysis status (pending, processing, completed, failed)"
    )
    extract_nouns: bool = Field(..., description="Whether nouns were extracted")
    extract_entities: bool = Field(..., description="Whether entities were extracted")
    max_nouns: int = Field(..., description="Maximum nouns configured")
    min_frequency: int = Field(..., description="Minimum frequency configured")
    nouns_count: int = Field(..., description="Number of nouns extracted")
    entities_count: int = Field(..., description="Number of entities extracted")
    processing_duration: Optional[float] = Field(
        None, description="Processing time in seconds"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")
    started_at: Optional[datetime] = Field(None, description="Analysis start time")
    completed_at: Optional[datetime] = Field(
        None, description="Analysis completion time"
    )
    created_at: datetime = Field(..., description="Record creation time")
    updated_at: datetime = Field(..., description="Record update time")

    class Config:
        """Pydantic config."""

        from_attributes = True


class AnalysisResultResponse(BaseModel):
    """Full analysis results for a content."""

    content_id: int = Field(..., description="Website content ID")
    url: str = Field(..., description="Content URL")
    language: Optional[str] = Field(None, description="Content language")
    word_count: int = Field(..., description="Total word count")
    status: str = Field(..., description="Analysis status")
    nouns: list[ExtractedNounResponse] = Field(
        default_factory=list, description="Extracted nouns"
    )
    entities: list[ExtractedEntityResponse] = Field(
        default_factory=list, description="Extracted named entities"
    )
    analyzed_at: Optional[datetime] = Field(None, description="Analysis completion time")
    processing_duration: Optional[float] = Field(
        None, description="Processing time in seconds"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True


class NounsSummaryResponse(BaseModel):
    """Summary response for nouns only."""

    content_id: int = Field(..., description="Website content ID")
    language: Optional[str] = Field(None, description="Content language")
    nouns: list[ExtractedNounResponse] = Field(..., description="Extracted nouns")
    total_count: int = Field(..., description="Total number of nouns")

    class Config:
        """Pydantic config."""

        from_attributes = True


class EntitiesSummaryResponse(BaseModel):
    """Summary response for entities only."""

    content_id: int = Field(..., description="Website content ID")
    language: Optional[str] = Field(None, description="Content language")
    entities: list[ExtractedEntityResponse] = Field(
        ..., description="Extracted entities"
    )
    total_count: int = Field(..., description="Total number of entities")
    entities_by_type: dict[str, int] = Field(
        default_factory=dict, description="Count of entities by type"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True


class BatchAnalysisResponse(BaseModel):
    """Response for batch analysis operations."""

    total_contents: int = Field(..., description="Total contents to analyze")
    started: int = Field(..., description="Number of analyses started")
    status: str = Field(
        ..., description="Batch status (queued, processing, completed)"
    )
    message: str = Field(..., description="Status message")

    class Config:
        """Pydantic config."""

        from_attributes = True


class AggregateNounResponse(BaseModel):
    """Aggregated noun data across multiple contents."""

    lemma: str = Field(..., description="Noun lemma")
    total_frequency: int = Field(..., description="Total frequency across all contents")
    avg_tfidf_score: float = Field(..., description="Average TF-IDF score")
    content_count: int = Field(
        ..., description="Number of contents containing this noun"
    )
    example_word: str = Field(..., description="Example word form")

    class Config:
        """Pydantic config."""

        from_attributes = True


class AggregateEntityResponse(BaseModel):
    """Aggregated entity data across multiple contents."""

    text: str = Field(..., description="Entity text")
    label: str = Field(..., description="Entity type")
    frequency: int = Field(..., description="Total frequency across all contents")
    content_count: int = Field(
        ..., description="Number of contents containing this entity"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True


class JobAggregateResponse(BaseModel):
    """Aggregated analysis results for a scraping job."""

    job_id: int = Field(..., description="Scraping job ID")
    total_contents: int = Field(..., description="Total contents analyzed")
    analyzed_contents: int = Field(..., description="Successfully analyzed contents")
    failed_contents: int = Field(..., description="Failed analyses")
    top_nouns: list[AggregateNounResponse] = Field(
        default_factory=list, description="Top nouns across all contents"
    )
    top_entities: list[AggregateEntityResponse] = Field(
        default_factory=list, description="Top entities across all contents"
    )
    entities_by_type: dict[str, int] = Field(
        default_factory=dict, description="Entity counts by type"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True


class AnalysisDeleteResponse(BaseModel):
    """Response for analysis deletion."""

    content_id: int = Field(..., description="Website content ID")
    deleted: bool = Field(..., description="Whether analysis was deleted")
    message: str = Field(..., description="Status message")

    class Config:
        """Pydantic config."""

        from_attributes = True
