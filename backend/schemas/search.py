"""Search schemas for request/response validation."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ScrapeConfig(BaseModel):
    """Scraping configuration schema."""

    depth: int = Field(1, ge=1, le=3, description="Scraping depth (1, 2, or 3)")
    max_urls_per_domain: int = Field(10, ge=1, le=100, description="Max URLs per domain for level 2")
    recollect: bool = Field(False, description="Force re-scraping of existing content")


class SearchExecuteRequest(BaseModel):
    """Request schema for executing searches."""

    session_name: str = Field(..., min_length=1, max_length=255, description="Name for the search session")
    queries: list[str] = Field(..., min_items=1, max_items=50, description="List of search queries")
    search_engine: str = Field("google_custom", description="Search engine to use")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results per query")
    language: str = Field("da", description="Language code (hl parameter) - defaults to Danish")
    country: str = Field("dk", description="Country code (gl parameter) - defaults to Denmark")
    allowed_domains: Optional[list[str]] = Field(None, description="Optional list of allowed domain TLDs")
    auto_scrape: bool = Field(False, description="Automatically start scraping after search")
    scrape_config: Optional[ScrapeConfig] = Field(None, description="Scraping configuration if auto_scrape is true")

    @field_validator("search_engine")
    @classmethod
    def validate_search_engine(cls, v: str) -> str:
        """Validate search engine."""
        allowed = ["google_custom", "serper"]
        if v not in allowed:
            raise ValueError(f"Search engine must be one of: {', '.join(allowed)}")
        return v

    @field_validator("allowed_domains")
    @classmethod
    def validate_domains(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate domain list."""
        if v is not None:
            for domain in v:
                if not domain.startswith("."):
                    raise ValueError(f"Domain '{domain}' must start with a dot (e.g., '.dk')")
        return v


class SearchExecuteResponse(BaseModel):
    """Response schema for search execution."""

    session_id: int
    task_id: Optional[str] = None
    status: str
    message: str
    status_url: Optional[str] = None

    model_config = {"from_attributes": True}


class SearchResultResponse(BaseModel):
    """Response schema for a single search result."""

    id: int
    url: str
    title: Optional[str]
    description: Optional[str]
    rank: int
    domain: str
    scraped: bool

    model_config = {"from_attributes": True}


class SearchQueryResponse(BaseModel):
    """Response schema for a search query."""

    id: int
    query_text: str
    search_engine: str
    max_results: int
    result_count: int
    status: str
    error_message: Optional[str] = None
    executed_at: Optional[datetime] = None
    results: Optional[list[SearchResultResponse]] = None

    model_config = {"from_attributes": True}


class SearchSessionResponse(BaseModel):
    """Response schema for a search session."""

    id: int
    name: str
    description: Optional[str]
    status: str
    query_count: int = 0
    website_count: int = 0
    scraped_count: int = 0
    analyzed_count: int = 0
    created_at: datetime
    updated_at: datetime
    queries: Optional[list[SearchQueryResponse]] = None

    model_config = {"from_attributes": True}


class SearchSessionDetailResponse(BaseModel):
    """Detailed response schema for a search session."""

    id: int
    name: str
    description: Optional[str]
    status: str
    config: Optional[dict] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    queries: list[SearchQueryResponse]

    model_config = {"from_attributes": True}


class SearchSessionListResponse(BaseModel):
    """Response schema for listing search sessions."""

    sessions: list[SearchSessionResponse]
    total: int
    page: int
    per_page: int
    pages: int
