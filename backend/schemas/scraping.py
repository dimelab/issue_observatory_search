"""Pydantic schemas for scraping operations."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ScrapingConfigBase(BaseModel):
    """Base configuration for scraping operations."""

    depth: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Scraping depth (1-3)",
    )
    domain_filter: str = Field(
        default="same_domain",
        description="Domain filter: same_domain, allow_all, or allow_tld_list",
    )
    allowed_tlds: Optional[list[str]] = Field(
        default=None,
        description="Allowed TLDs when domain_filter is allow_tld_list",
    )
    excluded_domains: Optional[list[str]] = Field(
        default=None,
        description="List of domains to exclude from scraping (e.g., ['linkedin.com', 'facebook.com'])",
    )
    delay_min: float = Field(
        default=2.0,
        ge=0.5,
        le=30.0,
        description="Minimum delay between requests (seconds)",
    )
    delay_max: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Maximum delay between requests (seconds)",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts",
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Request timeout (seconds)",
    )
    respect_robots_txt: bool = Field(
        default=True,
        description="Whether to respect robots.txt",
    )

    @field_validator("domain_filter")
    @classmethod
    def validate_domain_filter(cls, v: str) -> str:
        """Validate domain filter value."""
        allowed = ["same_domain", "allow_all", "allow_tld_list"]
        if v not in allowed:
            raise ValueError(f"domain_filter must be one of: {', '.join(allowed)}")
        return v

    @field_validator("delay_max")
    @classmethod
    def validate_delay_max(cls, v: float, info) -> float:
        """Validate that delay_max >= delay_min."""
        delay_min = info.data.get("delay_min", 0)
        if v < delay_min:
            raise ValueError("delay_max must be >= delay_min")
        return v


class ScrapingJobCreate(ScrapingConfigBase):
    """Schema for creating a scraping job."""

    session_id: int = Field(
        ...,
        gt=0,
        description="Search session ID to scrape",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Job name",
    )


class ScrapingJobResponse(BaseModel):
    """Schema for scraping job response."""

    id: int
    user_id: int
    session_id: int
    name: str
    status: str
    depth: int
    domain_filter: str
    allowed_tlds: Optional[list[str]]
    delay_min: float
    delay_max: float
    max_retries: int
    timeout: int
    respect_robots_txt: bool
    total_urls: int
    urls_scraped: int
    urls_failed: int
    urls_skipped: int
    current_depth: int
    celery_task_id: Optional[str]
    error_message: Optional[str]
    error_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_urls == 0:
            return 0.0
        return (self.urls_scraped / self.total_urls) * 100.0


class ScrapingJobList(BaseModel):
    """Schema for listing scraping jobs."""

    jobs: list[ScrapingJobResponse]
    total: int
    limit: int
    offset: int


class ScrapingJobStatistics(BaseModel):
    """Schema for scraping job statistics."""

    job_id: int
    status: str
    total_urls: int
    urls_scraped: int
    urls_failed: int
    urls_skipped: int
    current_depth: int
    progress_percentage: float
    total_content: int
    successful: int
    failed: int
    skipped: int
    avg_word_count: float
    total_words: int
    depth_distribution: dict[int, int]
    language_distribution: dict[str, int]
    started_at: Optional[str]
    completed_at: Optional[str]


class WebsiteContentResponse(BaseModel):
    """Schema for scraped website content."""

    id: int
    website_id: int
    user_id: int
    scraping_job_id: Optional[int]
    url: str
    html_content: Optional[str]
    extracted_text: Optional[str]
    title: Optional[str]
    meta_description: Optional[str]
    language: Optional[str]
    word_count: int
    scrape_depth: int
    parent_url: Optional[str]
    status: str
    error_message: Optional[str]
    outbound_links: Optional[list[str]]
    http_status_code: Optional[int]
    final_url: Optional[str]
    scrape_duration: Optional[float]
    scraped_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class WebsiteContentList(BaseModel):
    """Schema for listing scraped content."""

    content: list[WebsiteContentResponse]
    total: int
    limit: int
    offset: int


class ScrapingJobStart(BaseModel):
    """Schema for starting a scraping job."""

    job_id: int = Field(
        ...,
        gt=0,
        description="Scraping job ID to start",
    )


class ScrapingJobCancel(BaseModel):
    """Schema for cancelling a scraping job."""

    job_id: int = Field(
        ...,
        gt=0,
        description="Scraping job ID to cancel",
    )


class ScrapingJobStatus(BaseModel):
    """Schema for scraping job status."""

    status: str
    message: Optional[str] = None


class ScrapingError(BaseModel):
    """Schema for scraping error responses."""

    error: str
    details: Optional[str] = None
    code: str = "SCRAPING_ERROR"
