# Phase 7: Advanced Search Features - Implementation Guide

## Overview

Phase 7 implements comprehensive advanced search features for the Issue Observatory Search project, enabling sophisticated query formulation, snowballing, temporal analysis, and multi-perspective searching based on digital methods research.

**Completed:** October 24, 2025
**Version:** 1.0

## Architecture

### Core Components

1. **Query Expansion Module** (`backend/core/search/query_expansion.py`)
   - Implements snowballing methodology
   - Extracts related terms from multiple sources
   - Scores and ranks expansion candidates
   - Performance: <5s for 100 results

2. **Query Templates** (`backend/core/search/query_templates.py`)
   - Built-in framings for English and Danish
   - Custom template creation
   - Multi-perspective query generation
   - 8 predefined framing types

3. **SERP API Integration** (`backend/core/search_engines/serpapi.py`)
   - Unified interface for Google, Bing, DuckDuckGo
   - Token bucket rate limiting
   - Date range filtering
   - Device and locale targeting

4. **Domain Filtering** (`backend/core/search/domain_filter.py`)
   - Whitelist/blacklist filtering
   - TLD filtering
   - Sphere classification (8 spheres)
   - Pattern-based classification

5. **Temporal Search** (`backend/services/temporal_search_service.py`)
   - Date-filtered searches
   - Time period comparisons
   - Trend detection
   - Temporal snapshots

6. **Session Comparison** (`backend/services/session_comparison_service.py`)
   - URL and domain overlap
   - Ranking correlation (Spearman)
   - Sphere distribution
   - Discourse analysis

## Database Schema

### New Tables

**query_expansion_candidates**
- Stores expansion candidates with scores
- Tracks approval status and generation
- Fields: id, session_id, parent_query_id, candidate_term, score, source, metadata, approved, generation, created_at, approved_at, approved_by_user_id

**query_templates**
- User-defined and system templates
- Template variables and substitutions
- Fields: id, user_id, name, framing_type, template, variables, language, is_public, description, created_at, updated_at

**queries_from_templates**
- Links queries to templates
- Records variable substitutions
- Fields: id, template_id, search_query_id, substitutions, created_at

**bulk_search_uploads**
- CSV bulk search metadata
- Validation and execution tracking
- Fields: id, user_id, filename, row_count, validation_status, validation_errors, session_id, task_id, created_at, executed_at, completed_at

**bulk_search_rows**
- Individual bulk search rows
- Per-row status and errors
- Fields: id, upload_id, row_number, query_data, status, error_message, search_query_id

### Modified Tables

**search_queries** - Added fields:
- `date_from`, `date_to`: Temporal filtering
- `temporal_snapshot`: Marks snapshots for comparison
- `domain_whitelist`, `domain_blacklist`: Domain filters
- `tld_filter`: TLD filtering
- `sphere_filter`: Sphere filtering
- `framing_type`: Query framing classification
- `language`: Query language

## API Endpoints

### Query Expansion

```
POST /api/advanced-search/expand
```
Generate expansion candidates from a session.

**Request:**
```json
{
  "session_id": 123,
  "expansion_sources": ["search_results", "content", "suggestions"],
  "max_candidates": 100,
  "min_score": 0.1
}
```

**Response:**
```json
{
  "session_id": 123,
  "candidates": [
    {
      "id": 1,
      "candidate_term": "climate emergency",
      "score": 0.85,
      "source": "search_results,content",
      "metadata": {...},
      "approved": null,
      "generation": 1
    }
  ],
  "total_candidates": 45,
  "sources_used": ["search_results", "content"]
}
```

```
POST /api/advanced-search/expand/approve
```
Approve or reject expansion candidates.

```
POST /api/advanced-search/expand/execute
```
Execute searches for approved candidates.

### Query Templates

```
GET /api/advanced-search/templates
```
List available templates (with language/framing filters).

```
POST /api/advanced-search/templates
```
Create custom template.

**Request:**
```json
{
  "name": "Location-specific climate queries",
  "framing_type": "local",
  "template": "{issue} in {location}",
  "language": "en",
  "is_public": false,
  "description": "Generate location-specific queries"
}
```

```
POST /api/advanced-search/templates/{template_id}/apply
```
Apply template with substitutions.

```
POST /api/advanced-search/multi-perspective
```
Generate multi-perspective search across all framings.

**Request:**
```json
{
  "issue": "climate change",
  "language": "en",
  "framings": ["neutral", "activist", "skeptic", "scientific"],
  "location": "Denmark",
  "search_engine": "google_custom",
  "max_results": 50
}
```

### Session Comparison

```
POST /api/advanced-search/sessions/compare
```
Compare multiple sessions.

**Request:**
```json
{
  "session_ids": [123, 124, 125],
  "comparison_type": "full"
}
```

**Response:**
```json
{
  "session_ids": [123, 124, 125],
  "session_names": ["Session A", "Session B", "Session C"],
  "url_comparison": {
    "total_unique_urls": 150,
    "common_urls_count": 25,
    "similarities": [
      {"session_pair": "0 vs 1", "jaccard_similarity": 0.35}
    ]
  },
  "domain_comparison": {...},
  "ranking_comparison": {...},
  "sphere_comparison": {...},
  "discourse_comparison": {...}
}
```

### Temporal Search

```
POST /api/advanced-search/temporal/search
```
Execute date-filtered search.

```
POST /api/advanced-search/temporal/compare
```
Compare multiple time periods.

**Request:**
```json
{
  "query": "climate policy",
  "periods": [
    {"start": "2020-01-01T00:00:00Z", "end": "2020-12-31T23:59:59Z"},
    {"start": "2023-01-01T00:00:00Z", "end": "2023-12-31T23:59:59Z"}
  ],
  "search_engine": "google_custom",
  "max_results": 50
}
```

### Bulk Search

```
POST /api/bulk-search/upload
```
Upload and validate CSV file.

**CSV Format:**
```csv
query,framing,language,max_results,date_from,date_to,tld_filter,search_engine
"climate change",neutral,en,50,2023-01-01,2024-01-01,.dk,google_custom
"climate crisis",activist,en,50,,,".dk|.se",serper
```

```
POST /api/bulk-search/execute/{upload_id}
```
Execute validated bulk search.

```
GET /api/bulk-search/status/{task_id}
```
Get execution progress.

```
GET /api/bulk-search/results/{upload_id}
```
Get results summary.

## Celery Tasks

All async operations implemented as Celery tasks:

- `query_expansion_task`: Generate expansion candidates
- `bulk_search_task`: Execute bulk CSV searches
- `temporal_snapshot_task`: Archive temporal snapshot
- `session_comparison_task`: Complex session comparison

## Configuration

Add to `.env`:

```bash
# SERP API
SERPAPI_KEY=your_serpapi_key_here
SERPAPI_ENGINE=google  # google, bing, duckduckgo
SERPAPI_RATE_LIMIT=100  # per hour
SERPAPI_LOCATION=Denmark  # optional
```

## Query Expansion Algorithm

### Sources

1. **Search Results** (titles, descriptions, URLs)
   - Weight: Title = 3.0, Description = 2.0, URL = 1.5

2. **Content Analysis** (nouns, entities)
   - Weight: Entities = 3.0, Nouns = 2.5

3. **Search Suggestions** (autocomplete, related searches)
   - Weight: 2.0

### Scoring

Combined score = weighted average of:
- Frequency score (25%): Normalized term frequency
- Diversity score (20%): Number of different sources
- Position score (25%): Weighted by source importance
- Similarity score (20%): Cosine similarity to seed query
- TF-IDF bonus (10%): If available from content

### Filtering

- Minimum score threshold (default: 0.1)
- Minimum frequency (default: 2)
- Exclude seed query terms
- Exclude very short (<3) or long (>50) terms
- Exclude pure numbers

## Domain Sphere Classification

### Spheres

1. **Academia** - `.edu`, `.ac.uk`, research institutions
2. **Government** - `.gov`, `.gov.uk`, `.eu`, international orgs
3. **News** - Major news outlets (BBC, CNN, etc.)
4. **Activist** - NGOs, environmental groups
5. **Industry** - Corporate, business publications
6. **International** - UN, WHO, World Bank, etc.
7. **General** - Other domains
8. **Unknown** - Unclassified

### Classification Methods

1. **TLD-based** (95% confidence)
2. **Domain list matching** (85-90% confidence)
3. **Pattern matching** (50-60% confidence)
4. **Default** (30% confidence)

## Performance Characteristics

- Query expansion: <5s for 100 search results
- Bulk search: Handles 1000+ queries with rate limiting
- Session comparison: <10s for 2 sessions with 100 URLs each
- CSV parsing: <1s for 1000 rows
- SERP API: 100 requests/hour (configurable)

## Integration with Existing Phases

- **Phase 2** (Search): Extended with SERP API client
- **Phase 4** (Analysis): Uses nouns/entities for expansion
- **Phase 5** (Networks): Temporal filtering for network generation

## Example Workflows

### 1. Snowballing Search

```python
# Initial search
session = create_session("climate change", max_results=50)

# Generate expansion candidates
candidates = expand_query(session_id=session.id)

# Review and approve relevant terms
approve_candidates([1, 3, 5, 7])

# Execute approved expansions
expansion_session = execute_expansions(session.id, generation=1)

# Repeat for generation 2
```

### 2. Multi-Perspective Analysis

```python
# Generate queries for all framings
results = multi_perspective_search(
    issue="climate change",
    language="en",
    location="Denmark"
)

# Compare sessions
comparison = compare_sessions(
    session_ids=[results.neutral.id, results.activist.id, results.skeptic.id],
    comparison_type="full"
)

# Analyze discourse differences
print(comparison.discourse_comparison.shared_nouns)
print(comparison.discourse_comparison.unique_terms_by_session)
```

### 3. Temporal Trend Analysis

```python
# Execute temporal comparison
trends = compare_time_periods(
    query="climate policy",
    periods=[
        {"start": "2019-01-01", "end": "2019-12-31"},
        {"start": "2023-01-01", "end": "2023-12-31"}
    ]
)

# Analyze changes
print(trends.analysis.new_domains)
print(trends.analysis.disappeared_domains)
print(trends.analysis.url_overlaps)
```

## Testing

Run tests:
```bash
pytest tests/test_advanced_search.py -v
pytest tests/test_query_expansion.py -v
pytest tests/test_temporal_search.py -v
```

## Migration

Run migration:
```bash
alembic upgrade head
```

Rollback:
```bash
alembic downgrade -1
```

## Future Enhancements

1. Machine learning-based candidate scoring
2. LLM-powered query reformulation
3. Cross-language query translation (using proper translation API)
4. Real-time search suggestions API integration
5. Advanced sphere classification with ML
6. Automated framing detection
7. Visual query builder interface
8. Network-based expansion (use graph structure)
