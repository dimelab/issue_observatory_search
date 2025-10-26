"""Application configuration using Pydantic Settings."""
from typing import Optional
from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Issue Observatory Search"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # API
    api_v1_prefix: str = "/api"
    allowed_hosts: list[str] = ["*"]
    cors_origins: list[str] = ["*"]

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Database
    database_url: PostgresDsn
    database_echo: bool = False
    database_pool_size: int = 20  # Increased for better concurrency
    database_max_overflow: int = 10
    database_pool_recycle: int = 3600  # Recycle connections after 1 hour
    database_pool_pre_ping: bool = True  # Verify connections before use

    # Redis
    redis_url: RedisDsn
    redis_max_connections: int = 50  # Increased pool for caching

    # Celery
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None

    # External APIs
    google_custom_search_api_key: Optional[str] = None
    google_custom_search_engine_id: Optional[str] = None
    serper_api_key: Optional[str] = None  # Serper (google.serper.dev) API key

    # Phase 7: SERP API Configuration
    serpapi_key: Optional[str] = None
    serpapi_engine: str = "google"  # google, bing, duckduckgo
    serpapi_rate_limit: int = 100  # searches per hour
    serpapi_location: Optional[str] = None  # e.g., "Denmark" for localized results

    # OpenAI/LLM
    openai_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"

    # File Storage
    file_storage_path: str = "./data/exports"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 100
    rate_limit_search_per_minute: int = 10
    rate_limit_scrape_per_minute: int = 5
    rate_limit_network_per_hour: int = 5  # Network generation limit

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # NLP Configuration
    nlp_model_cache_size: int = 5
    nlp_batch_size: int = 10
    nlp_max_workers: int = 4
    nlp_cache_ttl: int = 3600  # 1 hour in seconds

    # Supported languages and their spaCy models
    nlp_languages: list[str] = ["en", "da"]
    spacy_model_en: str = "en_core_web_sm"
    spacy_model_da: str = "da_core_news_sm"

    # NLP processing limits
    nlp_max_text_length: int = 1000000  # 1M characters
    nlp_chunk_size: int = 100000  # Split large texts into chunks

    # Network Generation Configuration
    network_export_dir: str = "./data/networks"
    network_max_nodes: int = 10000  # Maximum nodes per network
    network_max_edges: int = 50000  # Maximum edges per network
    network_default_backboning_alpha: float = 0.05  # Default alpha for disparity filter
    network_cleanup_days: int = 30  # Days before cleanup of old networks
    network_default_top_n_nouns: int = 50  # Default top N nouns per website

    # Performance Settings - Caching
    cache_enabled: bool = True
    cache_default_ttl: int = 3600  # 1 hour
    cache_search_results_ttl: int = 3600  # 1 hour
    cache_network_metadata_ttl: int = 86400  # 24 hours
    cache_analysis_results_ttl: int = 3600  # 1 hour
    cache_user_preferences_ttl: int = 43200  # 12 hours
    cache_session_list_ttl: int = 300  # 5 minutes
    cache_statistics_ttl: int = 900  # 15 minutes

    # Performance Settings - Bulk Operations
    bulk_insert_chunk_size: int = 1000  # Records per bulk insert
    bulk_update_chunk_size: int = 1000  # Records per bulk update

    # Performance Settings - Pagination
    pagination_default_per_page: int = 50
    pagination_max_per_page: int = 500

    # Performance Settings - Query Optimization
    query_slow_threshold: float = 0.1  # Log queries slower than 100ms
    query_eager_loading: bool = True  # Enable eager loading by default

    # Performance Settings - Celery Worker
    celery_worker_prefetch_multiplier: int = 4
    celery_worker_max_tasks_per_child: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("celery_broker_url", mode="before")
    @classmethod
    def set_celery_broker(cls, v: Optional[str], info) -> str:
        """Set Celery broker URL from Redis URL if not provided."""
        if v is None:
            redis_url = info.data.get("redis_url")
            if redis_url:
                return str(redis_url)
        return v or ""

    @field_validator("celery_result_backend", mode="before")
    @classmethod
    def set_celery_result(cls, v: Optional[str], info) -> str:
        """Set Celery result backend from Redis URL if not provided."""
        if v is None:
            redis_url = info.data.get("redis_url")
            if redis_url:
                return str(redis_url)
        return v or ""


# Global settings instance
settings = Settings()
