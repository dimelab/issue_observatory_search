"""Schemas for Phase 7 advanced search features."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


# Query Expansion Schemas
class QueryExpansionRequest(BaseModel):
    """Request schema for query expansion."""

    session_id: int = Field(..., description="Session ID to expand from")
    expansion_sources: List[str] = Field(
        default=["search_results", "content", "suggestions"],
        description="Sources to use for expansion",
    )
    max_candidates: int = Field(100, ge=1, le=500, description="Maximum candidates to generate")
    min_score: float = Field(0.1, ge=0.0, le=1.0, description="Minimum score threshold")

    @field_validator("expansion_sources")
    @classmethod
    def validate_sources(cls, v: List[str]) -> List[str]:
        """Validate expansion sources."""
        valid = ["search_results", "content", "suggestions", "meta_keywords"]
        for source in v:
            if source not in valid:
                raise ValueError(f"Invalid source '{source}'. Valid: {', '.join(valid)}")
        return v


class QueryExpansionCandidateResponse(BaseModel):
    """Response schema for expansion candidate."""

    id: int
    candidate_term: str
    score: float
    source: str
    metadata: Optional[Dict[str, Any]] = None
    approved: Optional[bool] = None
    generation: int
    created_at: datetime

    model_config = {"from_attributes": True}


class QueryExpansionResponse(BaseModel):
    """Response schema for query expansion."""

    session_id: int
    candidates: List[QueryExpansionCandidateResponse]
    total_candidates: int
    sources_used: List[str]


class ApproveExpansionRequest(BaseModel):
    """Request schema for approving/rejecting candidates."""

    candidate_ids: List[int] = Field(..., description="Candidate IDs to approve/reject")
    approved: bool = Field(..., description="True to approve, False to reject")


class ExecuteExpansionRequest(BaseModel):
    """Request schema for executing approved expansions."""

    session_id: int
    search_engine: str = Field("google_custom", description="Search engine to use")
    max_results: int = Field(10, ge=1, le=100)
    generation: int = Field(1, ge=1, le=5, description="Generation number for new expansions")


# Query Template Schemas
class QueryTemplateCreate(BaseModel):
    """Request schema for creating query template."""

    name: str = Field(..., min_length=1, max_length=255)
    framing_type: str = Field(..., description="Type of framing")
    template: str = Field(..., description="Template string with {variables}")
    language: str = Field("en", description="Language code")
    is_public: bool = Field(False, description="Make template public")
    description: Optional[str] = None


class QueryTemplateResponse(BaseModel):
    """Response schema for query template."""

    id: int
    name: str
    framing_type: str
    template: str
    variables: Dict[str, Any]
    language: str
    is_public: bool
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplyTemplateRequest(BaseModel):
    """Request schema for applying template."""

    template_id: int
    substitutions: Dict[str, str] = Field(..., description="Variable substitutions")
    search_engine: str = Field("google_custom")
    max_results: int = Field(10, ge=1, le=100)
    create_session: bool = Field(True, description="Create new session for results")
    session_name: Optional[str] = None


class MultiPerspectiveRequest(BaseModel):
    """Request schema for multi-perspective search."""

    issue: str = Field(..., description="Main issue/topic")
    language: str = Field("en", description="Language code")
    framings: Optional[List[str]] = Field(None, description="Specific framings to use")
    location: Optional[str] = None
    year: Optional[str] = None
    search_engine: str = Field("google_custom")
    max_results: int = Field(10, ge=1, le=100)
    session_name: Optional[str] = None


# Session Comparison Schemas
class SessionComparisonRequest(BaseModel):
    """Request schema for session comparison."""

    session_ids: List[int] = Field(..., min_items=2, max_items=10)
    comparison_type: str = Field(
        "full",
        description="Type of comparison: full, urls, domains, discourse, rankings, spheres",
    )

    @field_validator("comparison_type")
    @classmethod
    def validate_comparison_type(cls, v: str) -> str:
        """Validate comparison type."""
        valid = ["full", "urls", "domains", "discourse", "rankings", "spheres"]
        if v not in valid:
            raise ValueError(f"Invalid type '{v}'. Valid: {', '.join(valid)}")
        return v


class SessionComparisonResponse(BaseModel):
    """Response schema for session comparison."""

    session_ids: List[int]
    session_names: List[str]
    comparison_type: str
    url_comparison: Optional[Dict[str, Any]] = None
    domain_comparison: Optional[Dict[str, Any]] = None
    ranking_comparison: Optional[Dict[str, Any]] = None
    sphere_comparison: Optional[Dict[str, Any]] = None
    discourse_comparison: Optional[Dict[str, Any]] = None


# Temporal Search Schemas
class TemporalSearchRequest(BaseModel):
    """Request schema for temporal search."""

    session_name: str = Field(..., min_length=1, max_length=255)
    queries: List[str] = Field(..., min_items=1, max_items=50)
    search_engine: str = Field("google_custom")
    max_results: int = Field(10, ge=1, le=100)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    temporal_snapshot: bool = Field(False, description="Mark as snapshot for comparison")


class TemporalComparisonRequest(BaseModel):
    """Request schema for comparing time periods."""

    query: str = Field(..., description="Query to search")
    periods: List[Dict[str, datetime]] = Field(
        ...,
        min_items=2,
        description="List of time periods with 'start' and 'end' keys",
    )
    search_engine: str = Field("google_custom")
    max_results: int = Field(50, ge=1, le=100)


# Bulk Search Schemas
class BulkSearchUploadRequest(BaseModel):
    """Request schema for bulk search CSV upload."""

    filename: str = Field(..., description="Original filename")
    validate_only: bool = Field(True, description="Only validate, don't execute")


class BulkSearchRowData(BaseModel):
    """Schema for bulk search row data."""

    query: str
    framing: Optional[str] = None
    language: Optional[str] = "en"
    max_results: int = Field(10, ge=1, le=100)
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    tld_filter: Optional[str] = None
    search_engine: str = Field("google_custom")


class BulkSearchValidationResponse(BaseModel):
    """Response schema for bulk search validation."""

    upload_id: int
    filename: str
    row_count: int
    validation_status: str
    validation_errors: Optional[Dict[str, Any]] = None
    valid_rows: int
    invalid_rows: int


class BulkSearchExecuteRequest(BaseModel):
    """Request schema for executing bulk search."""

    upload_id: int
    session_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class BulkSearchStatusResponse(BaseModel):
    """Response schema for bulk search status."""

    upload_id: int
    task_id: Optional[str]
    status: str
    total_rows: int
    completed_rows: int
    failed_rows: int
    progress_percentage: float


# Domain Filtering Schemas
class DomainFilterConfig(BaseModel):
    """Schema for domain filtering configuration."""

    whitelist: Optional[List[str]] = None
    blacklist: Optional[List[str]] = None
    tld_filter: Optional[List[str]] = None
    sphere_filter: Optional[List[str]] = None


class SphereClassificationResponse(BaseModel):
    """Response schema for sphere classification."""

    domain: str
    sphere: str
    confidence: float
    method: str


# Combined Advanced Search Request
class AdvancedSearchRequest(BaseModel):
    """Combined advanced search request with all features."""

    session_name: str = Field(..., min_length=1, max_length=255)
    queries: List[str] = Field(..., min_items=1, max_items=50)
    search_engine: str = Field("google_custom")
    max_results: int = Field(10, ge=1, le=100)

    # Temporal features
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    temporal_snapshot: bool = False

    # Domain filtering
    domain_filter: Optional[DomainFilterConfig] = None

    # Query formulation
    framing_type: Optional[str] = None
    language: Optional[str] = "en"

    # Auto-expansion
    auto_expand: bool = Field(False, description="Auto-generate expansion candidates")

    @field_validator("search_engine")
    @classmethod
    def validate_search_engine(cls, v: str) -> str:
        """Validate search engine."""
        allowed = ["google_custom", "serper", "serpapi_google", "serpapi_bing"]
        if v not in allowed:
            raise ValueError(f"Search engine must be one of: {', '.join(allowed)}")
        return v
