# Phase 4: Content Analysis - Quick Start Guide

## Installation (5 minutes)

```bash
# 1. Install dependencies
pip install -e .

# 2. Install spaCy models
python scripts/install_nlp_models.py

# 3. Run database migration
alembic upgrade head

# 4. Start Celery worker (in separate terminal)
celery -A backend.celery_app worker -Q analysis --loglevel=info

# 5. Start application
uvicorn backend.main:app --reload
```

## Quick Test

```bash
# Set your auth token
export TOKEN="your-jwt-token"

# Analyze a single content
curl -X POST http://localhost:8000/api/analysis/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": 1,
    "extract_nouns": true,
    "extract_entities": true,
    "max_nouns": 50
  }'

# Check status
curl http://localhost:8000/api/analysis/content/1/status \
  -H "Authorization: Bearer $TOKEN"

# Get results
curl http://localhost:8000/api/analysis/content/1 \
  -H "Authorization: Bearer $TOKEN"
```

## Common Operations

### Analyze Single Content

```python
from backend.services.analysis_service import AnalysisService

async with get_db() as session:
    service = AnalysisService(session)
    result = await service.analyze_content(
        content_id=123,
        extract_nouns=True,
        extract_entities=True,
        max_nouns=100
    )
```

### Batch Analysis

```python
result = await service.analyze_batch(
    content_ids=[1, 2, 3, 4, 5],
    extract_nouns=True,
    extract_entities=True
)
```

### Get Job Aggregate

```python
aggregate = await service.get_job_aggregate(
    job_id=456,
    top_n=50
)
```

## API Endpoints Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analysis/analyze` | Analyze single content |
| POST | `/api/analysis/batch` | Batch analysis |
| POST | `/api/analysis/job/{id}` | Analyze entire job |
| GET | `/api/analysis/content/{id}` | Get full results |
| GET | `/api/analysis/content/{id}/status` | Get status |
| GET | `/api/analysis/content/{id}/nouns` | Get nouns only |
| GET | `/api/analysis/content/{id}/entities` | Get entities only |
| GET | `/api/analysis/job/{id}/aggregate` | Get job aggregate |
| DELETE | `/api/analysis/content/{id}` | Delete analysis |

## Configuration

Key settings in `backend/config.py` or environment variables:

```bash
NLP_BATCH_SIZE=10           # Documents per batch
NLP_MAX_WORKERS=4           # Parallel workers
NLP_CACHE_TTL=3600          # Cache TTL (seconds)
NLP_MODEL_CACHE_SIZE=5      # Max models in memory
```

## Troubleshooting

### Model not found error

```bash
python -m spacy download en_core_web_sm
python -m spacy download da_core_news_sm
```

### Check if models are installed

```bash
python -m spacy validate
```

### Clear cache

```python
from backend.core.nlp.cache import get_analysis_cache
cache = await get_analysis_cache()
await cache.clear_all_analysis_cache()
```

### Monitor Celery tasks

```bash
# In separate terminal
celery -A backend.celery_app events

# Or use Flower
celery -A backend.celery_app flower
# Visit http://localhost:5555
```

## Performance Tips

1. **Use batch processing** for multiple documents (10-50x faster)
2. **Enable caching** - results cached for 1 hour
3. **Background tasks** for large batches (use `?background=true`)
4. **Increase workers** if processing is slow
5. **Monitor memory** - reduce batch size if high

## Common Use Cases

### Analyze after scraping

```python
# After scraping completes
from backend.tasks.analysis_tasks import analyze_job_task

task = analyze_job_task.delay(
    job_id=123,
    extract_nouns=True,
    extract_entities=True
)
```

### Get top terms for a job

```python
aggregate = await service.get_job_aggregate(job_id=123, top_n=20)
top_nouns = aggregate.top_nouns  # Sorted by frequency
```

### Find entities by type

```python
entities = await service.get_entities(
    content_id=123,
    label="PERSON",  # Filter by type
    limit=50
)
```

## File Locations

- **NLP Core**: `backend/core/nlp/`
- **Models**: `backend/models/analysis.py`
- **Service**: `backend/services/analysis_service.py`
- **API**: `backend/api/analysis.py`
- **Tasks**: `backend/tasks/analysis_tasks.py`
- **Config**: `backend/config.py`
- **Migration**: `migrations/versions/f9a1b2c3d4e5_add_analysis_tables.py`

## Support

- **API Docs**: http://localhost:8000/docs
- **Full Guide**: `PHASE4_ANALYSIS_GUIDE.md`
- **Implementation**: `PHASE4_IMPLEMENTATION_SUMMARY.md`

## Next Steps

1. ✅ Installation complete
2. ✅ Test with sample content
3. ✅ Check API documentation
4. ✅ Review full guide for advanced features
5. ⬜ Integrate with your scraping workflow
6. ⬜ Add custom visualization
7. ⬜ Set up monitoring

---

**Quick Start Time**: 5 minutes
**Full Feature Tour**: 30 minutes
**Production Ready**: Yes
