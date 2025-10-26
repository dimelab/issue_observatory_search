# Advanced Search Features - User Guide

## Introduction

This guide explains how to use the advanced search features in the Issue Observatory Search platform. These features enable sophisticated query formulation, iterative snowballing, temporal analysis, and multi-perspective searching for digital methods research.

## Table of Contents

1. [Query Snowballing](#query-snowballing)
2. [Query Templates and Framings](#query-templates-and-framings)
3. [Temporal Search](#temporal-search)
4. [Session Comparison](#session-comparison)
5. [Domain Filtering](#domain-filtering)
6. [Bulk Search](#bulk-search)
7. [Best Practices](#best-practices)

## Query Snowballing

Snowballing is the process of iteratively expanding your search by finding related terms from initial results. This helps discover broader contexts and related discourse.

### Basic Workflow

1. **Execute Initial Search**
   ```
   POST /api/search/execute
   {
     "session_name": "Climate Change Initial Search",
     "queries": ["climate change", "global warming"],
     "search_engine": "google_custom",
     "max_results": 50
   }
   ```

2. **Generate Expansion Candidates**
   ```
   POST /api/advanced-search/expand
   {
     "session_id": 123,
     "expansion_sources": ["search_results", "content"],
     "max_candidates": 100,
     "min_score": 0.1
   }
   ```

   **Expansion Sources:**
   - `search_results`: Extract from titles, descriptions, URLs
   - `content`: Use analyzed nouns and entities from scraped pages
   - `suggestions`: Use search engine autocomplete
   - `meta_keywords`: Extract from page metadata

3. **Review Candidates**
   Candidates are scored 0.0-1.0 based on:
   - Frequency across sources
   - Source diversity
   - TF-IDF scores
   - Similarity to original query

4. **Approve Relevant Terms**
   ```
   POST /api/advanced-search/expand/approve
   {
     "candidate_ids": [1, 3, 5, 7, 9],
     "approved": true
   }
   ```

5. **Execute Expansion Searches**
   ```
   POST /api/advanced-search/expand/execute
   {
     "session_id": 123,
     "search_engine": "google_custom",
     "max_results": 50,
     "generation": 1
   }
   ```

6. **Repeat for Multiple Generations**
   - Generation 1: Expand from initial search
   - Generation 2: Expand from generation 1 results
   - Continue until saturation

### Tips for Effective Snowballing

- **Start narrow**: Begin with specific, well-defined queries
- **Review carefully**: Not all high-scoring candidates are relevant
- **Track generations**: Use generation numbers to understand expansion depth
- **Monitor saturation**: Stop when new candidates become irrelevant
- **Combine sources**: Use multiple expansion sources for better coverage

## Query Templates and Framings

Templates enable systematic query formulation with different perspectives or framings.

### Built-in Framings

We provide 9 built-in framing types:

1. **Neutral**: Objective terminology
   - Example: "climate change", "global warming"

2. **Activist**: Action-oriented language
   - Example: "climate crisis", "climate emergency", "fight climate change"

3. **Skeptic**: Questioning framing
   - Example: "climate skepticism", "climate debate", "climate controversy"

4. **Scientific**: Research-focused terms
   - Example: "climate research", "climate science", "peer review"

5. **Policy**: Governance perspective
   - Example: "climate policy", "climate regulation", "climate legislation"

6. **Industry**: Business/economic framing
   - Example: "climate business", "green economy", "ESG investing"

7. **Media**: News/coverage perspective
   - Example: "climate news", "climate coverage", "climate report"

8. **Local**: Geographic specificity
   - Example: "climate change in Denmark", "Denmark climate impact"

9. **Temporal**: Time-based framing
   - Example: "climate change 2024", "future of climate"

### Using Multi-Perspective Search

Generate queries for all framings simultaneously:

```
POST /api/advanced-search/multi-perspective
{
  "issue": "climate change",
  "language": "en",
  "framings": ["neutral", "activist", "skeptic", "scientific"],
  "location": "Denmark",
  "year": "2024",
  "search_engine": "google_custom",
  "max_results": 50
}
```

This creates separate sessions for each framing, enabling comparative analysis.

### Creating Custom Templates

Define your own templates with variables:

```
POST /api/advanced-search/templates
{
  "name": "Regional Impact Analysis",
  "framing_type": "local",
  "template": "{issue} impact on {region} {sector}",
  "language": "en",
  "is_public": false,
  "description": "Analyze regional and sectoral impacts"
}
```

Apply with substitutions:

```
POST /api/advanced-search/templates/456/apply
{
  "substitutions": {
    "issue": "climate change",
    "region": "Nordic countries",
    "sector": "agriculture"
  },
  "search_engine": "google_custom",
  "max_results": 50
}
```

### Language Support

Currently supported:
- **English** (en): All framings
- **Danish** (da): All framings with localized terminology

Example Danish multi-perspective:
```
POST /api/advanced-search/multi-perspective
{
  "issue": "klimaændringer",
  "language": "da",
  "framings": ["neutral", "activist"],
  "location": "Danmark"
}
```

## Temporal Search

Analyze how search results change over time.

### Date-Filtered Search

```
POST /api/advanced-search/temporal/search
{
  "session_name": "Climate Policy 2023",
  "queries": ["climate policy", "climate regulation"],
  "search_engine": "google_custom",
  "max_results": 50,
  "date_from": "2023-01-01T00:00:00Z",
  "date_to": "2023-12-31T23:59:59Z",
  "temporal_snapshot": true
}
```

**Parameters:**
- `date_from`: Start date (ISO 8601 format)
- `date_to`: End date (ISO 8601 format)
- `temporal_snapshot`: Mark for later comparison

### Time Period Comparison

Compare results across multiple periods:

```
POST /api/advanced-search/temporal/compare
{
  "query": "climate policy",
  "periods": [
    {
      "start": "2019-01-01T00:00:00Z",
      "end": "2019-12-31T23:59:59Z"
    },
    {
      "start": "2023-01-01T00:00:00Z",
      "end": "2023-12-31T23:59:59Z"
    }
  ],
  "search_engine": "google_custom",
  "max_results": 100
}
```

**Returns:**
- URL overlap between periods
- Domain changes (new/disappeared)
- Ranking volatility
- Emerging/declining trends

### Trend Detection

Automatically detects:
- **Emerging domains**: Appear in later periods
- **Declining domains**: Disappear in later periods
- **Stable domains**: Consistent across periods

## Session Comparison

Compare multiple search sessions to analyze differences.

### Comparison Types

1. **Full**: All comparison metrics
2. **URLs**: URL overlap and Jaccard similarity
3. **Domains**: Domain overlap and diversity
4. **Rankings**: Ranking differences and correlations
5. **Spheres**: Sphere distribution comparison
6. **Discourse**: Noun/entity differences

### Basic Comparison

```
POST /api/advanced-search/sessions/compare
{
  "session_ids": [123, 124, 125],
  "comparison_type": "full"
}
```

### Understanding Results

**URL Comparison:**
- `total_unique_urls`: All unique URLs across sessions
- `common_urls_count`: URLs in all sessions
- `jaccard_similarity`: 0.0-1.0 similarity score (higher = more overlap)

**Domain Comparison:**
- `domain_diversity`: Shannon entropy (higher = more diverse)
- `common_domains`: Domains in all sessions

**Ranking Comparison:**
- `spearman_correlation`: -1.0 to 1.0 (1.0 = identical rankings)
- `ranking_volatility`: Ranking differences for shared URLs

**Discourse Comparison:**
- `shared_nouns`: Nouns appearing in all sessions
- `shared_entities`: Entities appearing in all sessions
- Session-specific terms

### Use Cases

1. **Framing Comparison**: Compare neutral vs. activist framings
2. **Engine Comparison**: Google vs. Bing results
3. **Temporal Comparison**: Same query, different time periods
4. **Geographic Comparison**: Same issue, different locations

## Domain Filtering

Filter search results by domain characteristics.

### TLD Filtering

Restrict to specific top-level domains:

```json
{
  "queries": ["climate change"],
  "tld_filter": [".dk", ".se", ".no"]
}
```

### Sphere Filtering

Filter by institutional sphere:

**Available spheres:**
- `academia`: Universities, research institutions
- `government`: Government websites
- `news`: News organizations
- `activist`: NGOs, advocacy groups
- `industry`: Corporate sites
- `international`: UN, WHO, etc.
- `general`: Other domains

```json
{
  "queries": ["climate policy"],
  "sphere_filter": ["government", "academia", "international"]
}
```

### Domain Whitelist/Blacklist

Explicit domain filtering:

```json
{
  "queries": ["climate change"],
  "domain_whitelist": ["*.bbc.co.uk", "*.nytimes.com"],
  "domain_blacklist": ["spam-site.com"]
}
```

**Whitelist supports:**
- Exact match: `example.com`
- Wildcard: `*.example.com`

## Bulk Search

Execute hundreds of searches from a CSV file.

### CSV Format

```csv
query,framing,language,max_results,date_from,date_to,tld_filter,search_engine
"climate change",neutral,en,50,2023-01-01,2024-01-01,.dk,google_custom
"climate crisis",activist,en,50,,,".dk|.se",serper
"climate policy",policy,da,30,,,".dk",google_custom
```

**Required columns:**
- `query`: Search query (required)

**Optional columns:**
- `framing`: Framing type
- `language`: Language code
- `max_results`: Results per query (1-100)
- `date_from`: Start date (YYYY-MM-DD)
- `date_to`: End date (YYYY-MM-DD)
- `tld_filter`: TLDs separated by `|`
- `search_engine`: Engine to use

### Upload and Validate

```
POST /api/bulk-search/upload
Content-Type: multipart/form-data

file: [CSV file]
validate_only: true
```

**Response:**
```json
{
  "upload_id": 789,
  "filename": "climate_queries.csv",
  "row_count": 150,
  "validation_status": "valid",
  "valid_rows": 148,
  "invalid_rows": 2,
  "validation_errors": {
    "row_15": ["max_results must be between 1 and 100"],
    "row_67": ["TLD '.com' must start with a dot"]
  }
}
```

### Execute Bulk Search

```
POST /api/bulk-search/execute/789
{
  "session_name": "Climate Multi-Query Analysis",
  "description": "150 climate-related queries"
}
```

**Returns:**
```json
{
  "upload_id": 789,
  "task_id": "abc-123-def-456",
  "status": "processing",
  "status_url": "/api/bulk-search/status/abc-123-def-456"
}
```

### Monitor Progress

```
GET /api/bulk-search/status/abc-123-def-456
```

**Response:**
```json
{
  "upload_id": 789,
  "task_id": "abc-123-def-456",
  "status": "processing",
  "total_rows": 150,
  "completed_rows": 75,
  "failed_rows": 2,
  "progress_percentage": 51.33
}
```

### Get Results

```
GET /api/bulk-search/results/789
```

## Best Practices

### Query Formulation

1. **Start Specific**: Begin with well-defined, specific queries
2. **Use Multiple Framings**: Capture different perspectives
3. **Combine Languages**: For bilingual/multilingual analysis
4. **Document Decisions**: Track why you approved/rejected candidates

### Snowballing Strategy

1. **Define Stopping Criteria**: When to stop expanding
2. **Monitor Quality**: Review high-scoring candidates carefully
3. **Track Generations**: Maintain clear generation numbering
4. **Diversify Sources**: Use multiple expansion sources

### Temporal Analysis

1. **Choose Appropriate Periods**: Align with events/policy changes
2. **Consistent Snapshots**: Use same parameters across periods
3. **Account for Seasonality**: Consider time-of-year effects
4. **Document Context**: Note external events affecting results

### Session Comparison

1. **Compare Like with Like**: Same parameters where possible
2. **Use Multiple Metrics**: Don't rely on single comparison
3. **Consider Context**: Understand why differences exist
4. **Visualize Results**: Use provided metrics for visualization

### Performance Optimization

1. **Batch Operations**: Use bulk search for many queries
2. **Cache Results**: Temporal snapshots for later comparison
3. **Rate Limiting**: Respect API limits (100/hour for SERP API)
4. **Async Operations**: Use Celery tasks for long operations

## Troubleshooting

### Common Issues

**Expansion candidates irrelevant:**
- Increase `min_score` threshold
- Use more specific seed queries
- Reduce `max_candidates`

**Temporal search returns no results:**
- Check date format (ISO 8601)
- Verify search engine supports date filtering
- Expand date range

**Bulk search validation fails:**
- Check CSV format (UTF-8 encoding)
- Verify column names exact match
- Ensure TLDs start with dot

**Session comparison slow:**
- Reduce number of sessions
- Use specific comparison type instead of "full"
- Ensure content is analyzed (for discourse comparison)

## API Rate Limits

- **Google Custom Search**: 100 queries/day (free tier)
- **Serper API**: Varies by plan
- **SERP API**: 100 searches/hour (configurable)

## Support

For issues or questions:
- Check implementation guide: `docs/PHASE7_IMPLEMENTATION.md`
- Review API documentation: OpenAPI at `/api/docs`
- Contact: support@issue-observatory.org
