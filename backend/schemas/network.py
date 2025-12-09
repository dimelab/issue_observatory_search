"""Network schemas for Phase 6."""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict

# Import keyword and NER extraction configs from analysis schemas
from backend.schemas.analysis import KeywordExtractionConfig, NERExtractionConfig


# Backboning configuration
class NetworkBackboningConfig(BaseModel):
    """Configuration for network backboning algorithms."""

    enabled: bool = Field(
        default=False,
        description="Whether to apply backboning"
    )
    algorithm: Literal["disparity_filter", "threshold", "top_k"] = Field(
        default="disparity_filter",
        description="Backboning algorithm to use"
    )
    alpha: Optional[float] = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Significance level for disparity filter (0.0-1.0)"
    )
    min_edge_weight: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Minimum edge weight threshold"
    )
    threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Weight threshold for threshold filter"
    )
    k: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of edges to keep for top-k filter"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": True,
                "algorithm": "disparity_filter",
                "alpha": 0.05,
                "min_edge_weight": 0.01
            }
        }
    )


# Network generation request
class NetworkGenerateRequest(BaseModel):
    """Request schema for generating a network."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name for the network"
    )
    type: Literal[
        "search_website",
        "website_noun",       # Legacy support
        "website_keyword",    # Enhanced from website_noun
        "website_ner",        # NEW in v6.0.0
        "website_concept"
    ] = Field(
        ...,
        description="Type of network to generate"
    )
    session_ids: List[int] = Field(
        ...,
        min_length=1,
        description="List of search session IDs to include"
    )

    # Network-specific configuration (legacy, kept for backward compatibility)
    top_n_nouns: Optional[int] = Field(
        default=50,
        ge=1,
        le=500,
        description="Top N nouns per website (legacy, use keyword_config instead)"
    )
    languages: Optional[List[str]] = Field(
        default=None,
        description="Languages to include (None = all)"
    )
    min_tfidf_score: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        description="Minimum TF-IDF score (legacy, use keyword_config instead)"
    )
    aggregate_by_domain: Optional[bool] = Field(
        default=True,
        description="Aggregate URLs by domain"
    )
    weight_method: Optional[Literal["inverse_rank", "exponential_decay", "fixed"]] = Field(
        default="inverse_rank",
        description="Edge weight calculation method (search_website only)"
    )

    # v6.0.0: Enhanced keyword extraction configuration (for website_keyword networks)
    keyword_config: Optional[KeywordExtractionConfig] = Field(
        default=None,
        description="Configuration for keyword extraction (website_keyword networks)"
    )

    # v6.0.0: NER extraction configuration (for website_ner networks)
    ner_config: Optional[NERExtractionConfig] = Field(
        default=None,
        description="Configuration for NER extraction (website_ner networks)"
    )

    # Backboning configuration
    backboning: Optional[NetworkBackboningConfig] = Field(
        default=None,
        description="Backboning configuration"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Climate Search Network",
                    "type": "search_website",
                    "session_ids": [1, 2, 3],
                    "aggregate_by_domain": True,
                    "weight_method": "inverse_rank",
                    "backboning": {
                        "enabled": True,
                        "algorithm": "disparity_filter",
                        "alpha": 0.05
                    }
                },
                {
                    "name": "Website Keywords (RAKE)",
                    "type": "website_keyword",
                    "session_ids": [1, 2],
                    "keyword_config": {
                        "method": "rake",
                        "max_keywords": 30,
                        "max_phrase_length": 3
                    }
                },
                {
                    "name": "Website Named Entities",
                    "type": "website_ner",
                    "session_ids": [1, 2],
                    "ner_config": {
                        "extraction_method": "transformer",
                        "entity_types": ["PERSON", "ORG", "LOC"],
                        "confidence_threshold": 0.85
                    }
                }
            ]
        }
    )


# Network metadata
class NetworkMetadata(BaseModel):
    """Network metadata schema."""

    session_ids: List[int]
    top_n_nouns: Optional[int] = None
    languages: Optional[List[str]] = None
    min_tfidf_score: Optional[float] = None
    aggregate_by_domain: Optional[bool] = None
    weight_method: Optional[str] = None
    query_count: Optional[int] = None
    website_count: Optional[int] = None
    noun_count: Optional[int] = None


# Network statistics
class NetworkStatistics(BaseModel):
    """Detailed network statistics."""

    node_count: int
    edge_count: int
    density: float
    avg_degree: float
    min_degree: int = 0
    max_degree: int = 0
    node_types: Dict[str, int]
    connected_components: Optional[int] = None
    largest_component_size: Optional[int] = None
    avg_weight: Optional[float] = None
    min_weight: Optional[float] = None
    max_weight: Optional[float] = None


# Network response
class NetworkResponse(BaseModel):
    """Response schema for network details."""

    id: int
    user_id: int
    name: str
    type: str
    session_ids: List[int]
    file_path: str
    file_size: int
    node_count: int
    edge_count: int
    backboning_applied: bool
    backboning_algorithm: Optional[str] = None
    backboning_alpha: Optional[float] = None
    original_edge_count: Optional[int] = None
    backboning_statistics: Optional[Dict[str, Any]] = None
    network_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Network list response
class NetworkListResponse(BaseModel):
    """Response schema for network list."""

    total: int
    page: int
    per_page: int
    networks: List[NetworkResponse]


# Network generation task response
class NetworkGenerationTaskResponse(BaseModel):
    """Response for network generation task."""

    network_id: Optional[int] = Field(
        default=None,
        description="Network ID (if generation completed synchronously)"
    )
    task_id: str = Field(
        ...,
        description="Celery task ID for async generation"
    )
    status: str = Field(
        default="pending",
        description="Task status"
    )
    message: str = Field(
        default="Network generation started",
        description="Status message"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "abc123-def456-ghi789",
                "status": "pending",
                "message": "Network generation started. Check task status for progress."
            }
        }
    )


# Backboning statistics response
class BackboningStatistics(BaseModel):
    """Backboning algorithm statistics."""

    algorithm: str
    alpha: Optional[float] = None
    min_edge_weight: Optional[float] = None
    threshold: Optional[float] = None
    k: Optional[int] = None
    original_nodes: int
    original_edges: int
    backbone_nodes: int
    backbone_edges: int
    nodes_removed: int
    edges_removed: int
    edge_retention_rate: float

    model_config = ConfigDict(from_attributes=True)
