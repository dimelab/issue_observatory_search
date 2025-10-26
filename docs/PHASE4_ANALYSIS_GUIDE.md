# Phase 4: Content Analysis - Implementation Guide

This guide provides comprehensive information about the content analysis functionality implemented in Phase 4 of the Issue Observatory Search application.

## Overview

Phase 4 implements advanced NLP (Natural Language Processing) capabilities for analyzing scraped web content. The system extracts meaningful information from text using spaCy, including:

- **Noun Extraction**: Identifies and ranks important nouns using TF-IDF scoring
- **Named Entity Recognition (NER)**: Extracts entities like persons, organizations, locations, etc.
- **Batch Processing**: Efficiently analyzes multiple documents
- **Caching**: Redis-based caching for improved performance
- **Background Tasks**: Celery integration for async processing

## Architecture

### Component Structure

```
backend/
├── core/nlp/                     # NLP processing modules
│   ├── models.py                 # spaCy model management
│   ├── tfidf.py                  # TF-IDF calculation
│   ├── noun_extraction.py        # Noun extraction with ranking
│   ├── ner.py                    # Named entity recognition
│   ├── cache.py                  # Redis caching
│   └── batch.py                  # Batch processing
├── models/analysis.py            # Database models
├── schemas/analysis.py           # Pydantic schemas
├── repositories/                 # Data access layer
│   └── analysis_repository.py
├── services/                     # Business logic
│   └── analysis_service.py
├── tasks/                        # Celery background tasks
│   └── analysis_tasks.py
└── api/                          # REST endpoints
    └── analysis.py

migrations/versions/              # Database migrations
└── f9a1b2c3d4e5_add_analysis_tables.py

scripts/                          # Utility scripts
└── install_nlp_models.py         # spaCy model installer
```

## Installation

### 1. Install Dependencies

The NLP dependencies are already added to `setup.py`:

```bash
pip install -e .
```

Or install directly:

```bash
pip install spacy>=3.7.0 scikit-learn>=1.3.0 numpy>=1.24.0
```

### 2. Install spaCy Models

Run the installation script:

```bash
python scripts/install_nlp_models.py
```

Or install manually:

```bash
python -m spacy download en_core_web_sm  # English
python -m spacy download da_core_news_sm  # Danish
```

### 3. Run Database Migration

Apply the analysis tables migration:

```bash
alembic upgrade head
```

This creates three tables:
- `content_analysis` - Analysis metadata
- `extracted_nouns` - Extracted nouns with TF-IDF scores
- `extracted_entities` - Named entities

### 4. Start Celery Worker

Start a Celery worker for the analysis queue:

```bash
celery -A backend.celery_app worker -Q analysis --loglevel=info
```

## Configuration

Configuration is in `backend/config.py`:

```python
# NLP Configuration
nlp_model_cache_size: int = 5          # Max models in memory
nlp_batch_size: int = 10               # Documents per batch
nlp_max_workers: int = 4               # Parallel workers
nlp_cache_ttl: int = 3600              # Cache TTL (1 hour)

# Supported languages
nlp_languages: list[str] = ["en", "da"]
spacy_model_en: str = "en_core_web_sm"
spacy_model_da: str = "da_core_news_sm"

# Processing limits
nlp_max_text_length: int = 1000000     # 1M characters
nlp_chunk_size: int = 100000           # Chunk size for large texts
```

Environment variables (optional):

```bash
NLP_MODEL_CACHE_SIZE=5
NLP_BATCH_SIZE=10
NLP_MAX_WORKERS=4
NLP_CACHE_TTL=3600
SPACY_MODEL_EN=en_core_web_sm
SPACY_MODEL_DA=da_core_news_sm
```

## API Endpoints

All endpoints are under `/api/analysis` and require authentication.

### 1. Analyze Single Content

**POST** `/api/analysis/analyze`

Analyzes a single website content synchronously.

```json
{
  "content_id": 123,
  "extract_nouns": true,
  "extract_entities": true,
  "max_nouns": 100,
  "min_frequency": 2
}
```

Response:
```json
{
  "content_id": 123,
  "url": "https://example.com/page",
  "language": "en",
  "word_count": 1500,
  "status": "completed",
  "nouns": [
    {
      "word": "climate",
      "lemma": "climate",
      "frequency": 15,
      "tfidf_score": 0.453,
      "positions": [45, 123, 456]
    }
  ],
  "entities": [
    {
      "text": "United Nations",
      "label": "ORG",
      "start_pos": 234,
      "end_pos": 248,
      "confidence": null
    }
  ],
  "analyzed_at": "2025-10-23T23:30:00Z",
  "processing_duration": 2.34
}
```

### 2. Batch Analysis

**POST** `/api/analysis/batch?background=true`

Analyzes multiple contents. Can run synchronously or in background.

```json
{
  "content_ids": [123, 124, 125],
  "extract_nouns": true,
  "extract_entities": true,
  "max_nouns": 100,
  "min_frequency": 2
}
```

Response (background=true):
```json
{
  "total_contents": 3,
  "started": 3,
  "status": "queued",
  "message": "Batch analysis queued (task ID: abc-123)"
}
```

### 3. Analyze Entire Job

**POST** `/api/analysis/job/{job_id}`

Queues analysis for all contents in a scraping job.

```json
{
  "extract_nouns": true,
  "extract_entities": true,
  "max_nouns": 100,
  "min_frequency": 2
}
```

### 4. Get Analysis Results

**GET** `/api/analysis/content/{content_id}`

Returns complete analysis results for a content.

### 5. Get Analysis Status

**GET** `/api/analysis/content/{content_id}/status`

Returns analysis status and metadata without full results.

```json
{
  "content_id": 123,
  "status": "completed",
  "extract_nouns": true,
  "extract_entities": true,
  "nouns_count": 87,
  "entities_count": 45,
  "processing_duration": 2.34,
  "completed_at": "2025-10-23T23:30:00Z"
}
```

### 6. Get Nouns Only

**GET** `/api/analysis/content/{content_id}/nouns?limit=50`

Returns extracted nouns sorted by TF-IDF score.

### 7. Get Entities Only

**GET** `/api/analysis/content/{content_id}/entities?label=PERSON&limit=50`

Returns extracted entities, optionally filtered by type.

### 8. Get Job Aggregate

**GET** `/api/analysis/job/{job_id}/aggregate?top_n=50`

Returns aggregated analysis results across all contents in a job.

```json
{
  "job_id": 456,
  "total_contents": 100,
  "analyzed_contents": 95,
  "failed_contents": 5,
  "top_nouns": [
    {
      "lemma": "climate",
      "total_frequency": 234,
      "avg_tfidf_score": 0.453,
      "content_count": 78,
      "example_word": "climate"
    }
  ],
  "top_entities": [
    {
      "text": "United Nations",
      "label": "ORG",
      "frequency": 45,
      "content_count": 32
    }
  ],
  "entities_by_type": {
    "ORG": 156,
    "PERSON": 89,
    "GPE": 234
  }
}
```

### 9. Delete Analysis

**DELETE** `/api/analysis/content/{content_id}`

Deletes analysis results for a content (not the content itself).

## Core Components

### 1. NLP Model Manager (`backend/core/nlp/models.py`)

Manages spaCy models with caching:

```python
from backend.core.nlp.models import nlp_model_manager

# Get model (cached)
nlp = await nlp_model_manager.get_model("en")

# Check if model is available
available = await nlp_model_manager.is_model_available("da")

# Clear cache
await nlp_model_manager.clear_cache()
```

**Features**:
- Singleton pattern for shared model instances
- Thread-safe loading with asyncio locks
- Lazy loading on first use
- Automatic pipeline optimization

### 2. TF-IDF Calculator (`backend/core/nlp/tfidf.py`)

Calculates term importance scores:

```python
from backend.core.nlp.tfidf import TFIDFCalculator

calculator = TFIDFCalculator()

# Calculate for document
document = ["python", "programming", "python"]
corpus = [document, ["java", "programming"], ["python", "coding"]]

scores = await calculator.calculate_for_document(document, corpus)
# {"python": 0.234, "programming": 0.123, ...}

# Get top terms
top_terms = calculator.get_top_terms(scores, top_n=10)
```

### 3. Noun Extractor (`backend/core/nlp/noun_extraction.py`)

Extracts and ranks nouns:

```python
from backend.core.nlp.noun_extraction import NounExtractor

extractor = NounExtractor()

nouns = await extractor.extract_nouns(
    text="Python programming is great. Python is versatile.",
    language="en",
    max_nouns=100,
    min_frequency=2
)

# Batch extraction
texts = ["Text 1", "Text 2", "Text 3"]
results = await extractor.extract_nouns_batch(texts, language="en")
```

**ExtractedNoun**:
- `word`: Original word form
- `lemma`: Base form (e.g., "running" → "run")
- `frequency`: Occurrence count
- `tfidf_score`: Importance score
- `positions`: Character positions in text

### 4. Named Entity Extractor (`backend/core/nlp/ner.py`)

Extracts named entities:

```python
from backend.core.nlp.ner import NamedEntityExtractor

extractor = NamedEntityExtractor()

entities = await extractor.extract_entities(
    text="Apple Inc. was founded by Steve Jobs.",
    language="en",
    entity_types=["PERSON", "ORG"]
)

# Get counts by type
counts = await extractor.extract_entities_with_counts(text)
# {"PERSON": {"Steve Jobs": 1}, "ORG": {"Apple Inc.": 1}}
```

**Entity Types**:
- PERSON - People
- ORG - Organizations
- GPE - Countries, cities
- LOC - Non-GPE locations
- DATE - Dates
- EVENT - Named events
- PRODUCT - Products

### 5. Analysis Cache (`backend/core/nlp/cache.py`)

Redis-based caching:

```python
from backend.core.nlp.cache import get_analysis_cache

cache = await get_analysis_cache()

# Cache analysis
await cache.cache_analysis(content_id, results)

# Get cached analysis
cached = await cache.get_cached_analysis(content_id)

# Invalidate cache
await cache.invalidate_analysis(content_id)

# Get stats
stats = await cache.get_cache_stats()
```

### 6. Batch Analyzer (`backend/core/nlp/batch.py`)

Efficient batch processing:

```python
from backend.core.nlp.batch import BatchAnalyzer

analyzer = BatchAnalyzer(batch_size=10, max_workers=4)

# Process batch
texts = ["Text 1", "Text 2", ...]
results = await analyzer.process_batch(
    texts=texts,
    language="en",
    extract_nouns=True,
    extract_entities=True,
    content_ids=[1, 2, ...]
)

# Get statistics
stats = analyzer.get_statistics(results)
```

## Database Schema

### content_analysis

Metadata about analysis operations:

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| website_content_id | Integer | FK to website_content (unique) |
| extract_nouns | Boolean | Whether nouns extracted |
| extract_entities | Boolean | Whether entities extracted |
| max_nouns | Integer | Max nouns configured |
| min_frequency | Integer | Min frequency configured |
| nouns_count | Integer | Number of nouns extracted |
| entities_count | Integer | Number of entities extracted |
| status | String(20) | pending/processing/completed/failed |
| error_message | Text | Error if failed |
| processing_duration | Float | Time in seconds |
| started_at | DateTime | Analysis start time |
| completed_at | DateTime | Analysis completion time |

### extracted_nouns

Extracted nouns with rankings:

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| website_content_id | Integer | FK to website_content |
| word | String(255) | Original word form |
| lemma | String(255) | Lemmatized form |
| frequency | Integer | Occurrence count |
| tfidf_score | Float | Importance score |
| positions | JSON | Character positions array |
| language | String(10) | Language code |

**Indexes**:
- website_content_id
- word, lemma
- tfidf_score
- language
- Composite: (website_content_id, tfidf_score)

### extracted_entities

Named entities:

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| website_content_id | Integer | FK to website_content |
| text | String(500) | Entity text |
| label | String(50) | Entity type |
| start_pos | Integer | Start position |
| end_pos | Integer | End position |
| confidence | Float | Optional confidence score |
| language | String(10) | Language code |

**Indexes**:
- website_content_id
- text, label
- language
- Composite: (website_content_id, label)

## Performance Optimization

### Caching Strategy

1. **Model Caching**: spaCy models cached in memory (singleton pattern)
2. **Result Caching**: Analysis results cached in Redis (1 hour TTL)
3. **Query Caching**: Database queries use eager loading to avoid N+1

### Batch Processing

- Process multiple documents in parallel (configurable workers)
- Share NLP models across batch
- Use corpus for better TF-IDF calculation
- Progress tracking and error isolation

### Database Optimization

- Indexes on foreign keys and frequently queried columns
- Bulk inserts for nouns and entities
- Composite indexes for common query patterns
- Connection pooling (pool_size=5, max_overflow=10)

### Performance Targets

✅ Extract nouns from 1,000 words in < 1 second
✅ Process 100 documents in < 30 seconds (batch)
✅ Model loading < 5 seconds
✅ Cache hit rate > 80% for repeated analysis

## Error Handling

### Common Errors and Solutions

1. **Model Not Installed**
   ```
   RuntimeError: spaCy model 'en_core_web_sm' is not installed
   ```
   **Solution**: Run `python scripts/install_nlp_models.py`

2. **Language Not Supported**
   ```
   ValueError: Language 'fr' not supported
   ```
   **Solution**: Add language to config and install model

3. **Text Too Large**
   - Automatic truncation to `nlp_max_text_length`
   - Logged as warning

4. **Memory Issues**
   - Reduce `nlp_batch_size`
   - Reduce `nlp_max_workers`
   - Clear model cache periodically

## Testing

### Unit Tests

Run the analysis tests:

```bash
pytest tests/test_analysis.py -v
```

### Manual Testing

1. **Test single analysis**:
   ```bash
   curl -X POST http://localhost:8000/api/analysis/analyze \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"content_id": 123, "extract_nouns": true, "extract_entities": true}'
   ```

2. **Test batch analysis**:
   ```bash
   curl -X POST "http://localhost:8000/api/analysis/batch?background=true" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"content_ids": [123, 124, 125]}'
   ```

3. **Check analysis status**:
   ```bash
   curl http://localhost:8000/api/analysis/content/123/status \
     -H "Authorization: Bearer $TOKEN"
   ```

## Monitoring

### Celery Monitoring

Monitor analysis tasks:

```bash
celery -A backend.celery_app events
```

Or use Flower:

```bash
celery -A backend.celery_app flower
```

### Cache Statistics

Get cache stats via API or directly:

```python
from backend.core.nlp.cache import get_analysis_cache

cache = await get_analysis_cache()
stats = await cache.get_cache_stats()
print(stats)
```

### Database Queries

Monitor slow queries in PostgreSQL:

```sql
-- Top 10 slowest queries
SELECT * FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

## Maintenance

### Cleanup Old Analyses

Schedule periodic cleanup:

```python
from backend.tasks.analysis_tasks import cleanup_old_analyses_task

# Clean analyses older than 30 days
cleanup_old_analyses_task.delay(days_old=30)
```

### Clear Cache

Clear all analysis cache:

```python
from backend.core.nlp.cache import get_analysis_cache

cache = await get_analysis_cache()
deleted = await cache.clear_all_analysis_cache()
```

### Re-analyze Content

To re-analyze content:

1. Delete existing analysis: `DELETE /api/analysis/content/{id}`
2. Run new analysis: `POST /api/analysis/analyze`

Or use `force_refresh=True` in service layer.

## Troubleshooting

### Issue: Models not loading

**Symptoms**: RuntimeError about missing models
**Solution**:
1. Verify installation: `python -m spacy validate`
2. Re-install: `python scripts/install_nlp_models.py`
3. Check file permissions

### Issue: Slow performance

**Symptoms**: Analysis takes > 5 seconds per document
**Solution**:
1. Check model cache: Are models being reloaded?
2. Reduce text length: Large documents take longer
3. Use batch processing for multiple documents
4. Check database indexes

### Issue: High memory usage

**Symptoms**: Worker OOM errors
**Solution**:
1. Reduce `nlp_model_cache_size`
2. Reduce `nlp_batch_size`
3. Reduce `nlp_max_workers`
4. Use worker auto-restart: `--max-tasks-per-child=100`

### Issue: Cache not working

**Symptoms**: Same documents analyzed repeatedly
**Solution**:
1. Check Redis connection
2. Verify `nlp_cache_ttl` is set
3. Check cache hit rate in logs

## Future Enhancements

Potential improvements:

1. **Additional Languages**: Add support for more languages
2. **Custom Entity Types**: Train custom NER models
3. **Topic Modeling**: LDA or similar for topic extraction
4. **Sentiment Analysis**: Add sentiment scoring
5. **Keyword Extraction**: TextRank or RAKE algorithms
6. **Document Similarity**: Compare documents
7. **Summarization**: Extractive or abstractive summaries
8. **Visualization**: Network graphs of entities
9. **Export**: Export analysis results (CSV, JSON, Excel)
10. **Webhooks**: Notify when analysis completes

## Support

For issues or questions:

1. Check the logs: `logs/analysis.log`
2. Review this documentation
3. Check the API documentation: `http://localhost:8000/docs`
4. File an issue on GitHub

## License

This implementation is part of the Issue Observatory Search project and follows the same license.
