"""
Pydantic schemas for content analysis operations.

Enhanced in v6.0.0 to support:
- Multiple keyword extraction methods (noun, all_pos, tfidf, rake)
- Transformer-based NER
- Configurable extraction parameters
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


# v6.0.0: Configuration Schemas for Enhanced Extraction


class KeywordExtractionConfig(BaseModel):
    """
    Configuration for keyword extraction methods.

    Supports:
    - noun: Original spaCy noun extraction (backward compatible)
    - all_pos: Extract nouns, verbs, adjectives
    - tfidf: TF-IDF with optional bigrams
    - rake: RAKE algorithm with n-grams
    """

    method: Literal["noun", "all_pos", "tfidf", "rake"] = Field(
        default="noun",
        description="Extraction method to use"
    )
    max_keywords: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of keywords to extract"
    )
    min_frequency: int = Field(
        default=2,
        ge=1,
        le=100,
        description="Minimum frequency for a keyword to be included"
    )

    # TF-IDF specific options
    use_bigrams: bool = Field(
        default=False,
        description="Include bigrams (2-word phrases) in TF-IDF extraction"
    )
    idf_weight: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="IDF weighting factor: 0.0 (pure TF) to 2.0 (IDF-heavy)"
    )

    # RAKE specific options
    max_phrase_length: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum phrase length (n-gram size) for RAKE extraction"
    )

    # POS filter options (for "all_pos" method)
    include_pos: list[str] = Field(
        default=["NOUN"],
        description="POS tags to include: NOUN, VERB, ADJ"
    )

    @field_validator("include_pos")
    @classmethod
    def validate_pos_tags(cls, v: list[str]) -> list[str]:
        """Validate that POS tags are supported."""
        allowed = {"NOUN", "VERB", "ADJ"}
        for tag in v:
            if tag not in allowed:
                raise ValueError(f"POS tag '{tag}' not supported. Use: {allowed}")
        return v

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "method": "rake",
                "max_keywords": 30,
                "min_frequency": 2,
                "max_phrase_length": 3
            }
        }


class NERExtractionConfig(BaseModel):
    """
    Configuration for Named Entity Recognition extraction.

    Supports:
    - spacy: Fast spaCy NER (existing)
    - transformer: Transformer-based multilingual NER (new)
    """

    extraction_method: Literal["spacy", "transformer"] = Field(
        default="spacy",
        description="NER extraction method to use"
    )
    entity_types: list[str] = Field(
        default=["PERSON", "ORG", "GPE", "LOC"],
        description="Entity types to extract (PERSON, ORG, GPE, LOC, MISC)"
    )
    confidence_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for including entities"
    )
    max_entities_per_content: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum entities to extract per content"
    )

    @field_validator("entity_types")
    @classmethod
    def validate_entity_types(cls, v: list[str]) -> list[str]:
        """Validate that entity types are supported."""
        allowed = {"PERSON", "PER", "ORG", "GPE", "LOC", "MISC"}
        for entity_type in v:
            if entity_type not in allowed:
                raise ValueError(
                    f"Entity type '{entity_type}' not supported. Use: {allowed}"
                )
        return v

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "extraction_method": "transformer",
                "entity_types": ["PERSON", "ORG", "LOC"],
                "confidence_threshold": 0.85,
                "max_entities_per_content": 100
            }
        }


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
    """
    Response schema for extracted keywords (formerly nouns).

    Enhanced in v6.0.0 with extraction method and phrase length information.
    """

    word: str = Field(..., description="Original word form or phrase")
    lemma: str = Field(..., description="Lemmatized (base) form of the word")
    frequency: int = Field(..., description="Number of times keyword appears")
    tfidf_score: float = Field(..., description="Importance score (TF-IDF or other)")
    positions: list[int] = Field(
        default_factory=list, description="Character positions in text"
    )

    # v6.0.0: New fields
    extraction_method: str = Field(
        default="noun",
        description="Extraction method: noun, all_pos, tfidf, rake"
    )
    phrase_length: Optional[int] = Field(
        None,
        description="Number of words in phrase (for n-grams)"
    )
    pos_tag: Optional[str] = Field(
        None,
        description="Part of speech tag (NOUN, VERB, ADJ, etc.)"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True


# Alias for clarity
ExtractedKeywordResponse = ExtractedNounResponse


class ExtractedEntityResponse(BaseModel):
    """
    Response schema for extracted named entities.

    Enhanced in v6.0.0 with extraction method and frequency information.
    """

    text: str = Field(..., description="Entity text")
    label: str = Field(..., description="Entity type (PERSON, ORG, GPE, LOC, MISC)")
    start_pos: int = Field(..., description="Character position where entity starts")
    end_pos: int = Field(..., description="Character position where entity ends")
    confidence: float = Field(
        default=1.0,
        description="Confidence score (0.0-1.0)"
    )

    # v6.0.0: New fields
    frequency: int = Field(
        default=1,
        description="Number of times this entity appears"
    )
    extraction_method: str = Field(
        default="spacy",
        description="Extraction method: spacy or transformer"
    )

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


# v6.0.0: Keyword Extraction Preview (Phase 5)


class KeywordPreviewRequest(BaseModel):
    """
    Request to preview keyword extraction results.

    Useful for testing different extraction methods and parameters
    before generating a full network.
    """

    sample_text: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Sample text to extract keywords from"
    )
    language: str = Field(
        default="en",
        description="Language code (en, da, etc.)"
    )
    config: KeywordExtractionConfig = Field(
        default_factory=KeywordExtractionConfig,
        description="Keyword extraction configuration"
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "sample_text": "Climate change is affecting global weather patterns...",
                "language": "en",
                "config": {
                    "method": "rake",
                    "max_keywords": 20,
                    "max_phrase_length": 3
                }
            }
        }


class KeywordPreviewItem(BaseModel):
    """A single keyword from preview results."""

    phrase: str = Field(..., description="Keyword or phrase")
    score: float = Field(..., description="Relevance score")
    word_count: int = Field(default=1, description="Number of words in phrase")
    pos_tag: Optional[str] = Field(None, description="Part of speech tag (if applicable)")


class KeywordPreviewResponse(BaseModel):
    """Response for keyword extraction preview."""

    keywords: list[KeywordPreviewItem] = Field(
        ...,
        description="Extracted keywords (top 20)"
    )
    config: KeywordExtractionConfig = Field(
        ...,
        description="Configuration used for extraction"
    )
    total_extracted: int = Field(
        ...,
        description="Total number of keywords extracted before limiting"
    )
    processing_time: float = Field(
        ...,
        description="Processing time in seconds"
    )

    class Config:
        """Pydantic config."""
        from_attributes = True
