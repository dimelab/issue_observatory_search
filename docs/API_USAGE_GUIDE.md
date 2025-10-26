# API Usage Guide

Complete guide to using the Issue Observatory Search API with detailed examples for all endpoints.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Search API](#search-api)
3. [Scraping API](#scraping-api)
4. [Analysis API](#analysis-api)
5. [Admin API](#admin-api)
6. [Error Handling](#error-handling)

---

## Authentication

All API endpoints (except `/health` and `/`) require JWT authentication.

### Create Admin User

When using Docker, create an admin user:

```bash
docker-compose exec backend python -c "
from backend.database import AsyncSessionLocal
from backend.models.user import User
from backend.utils.auth import get_password_hash
import asyncio

async def create_admin():
    async with AsyncSessionLocal() as db:
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=get_password_hash('admin123'),
            is_admin=True
        )
        db.add(admin)
        await db.commit()
        print('Admin user created!')

asyncio.run(create_admin())
"
```

### Login

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "is_admin": true,
    "is_active": true,
    "created_at": "2025-01-01T00:00:00"
  }
}
```

### Get Current User

```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Logout

```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## Search API

### Execute Search with Multiple Queries

**Using Serper (Recommended):**
```bash
curl -X POST http://localhost:8000/api/search/execute \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "Climate Change Research",
    "queries": ["climate change", "global warming", "carbon emissions"],
    "search_engine": "serper",
    "max_results": 20,
    "allowed_domains": [".edu", ".org"]
  }'
```

**Using Google Custom Search:**
```bash
curl -X POST http://localhost:8000/api/search/execute \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "Academic Research",
    "queries": ["machine learning", "deep learning"],
    "search_engine": "google_custom",
    "max_results": 10
  }'
```

**Response:**
```json
{
  "session_id": 1,
  "status": "completed",
  "message": "Search completed successfully",
  "status_url": "/api/search/session/1"
}
```

### List All Search Sessions

```bash
curl -X GET "http://localhost:8000/api/search/sessions?page=1&per_page=10" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Response:**
```json
{
  "sessions": [
    {
      "id": 1,
      "name": "Climate Change Research",
      "status": "completed",
      "query_count": 3,
      "website_count": 45,
      "created_at": "2025-01-15T10:30:00",
      "updated_at": "2025-01-15T10:35:00"
    }
  ],
  "total": 15,
  "page": 1,
  "per_page": 10,
  "pages": 2
}
```

### Get Session Details

```bash
curl -X GET http://localhost:8000/api/search/session/1 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Response:**
```json
{
  "id": 1,
  "name": "Climate Change Research",
  "status": "completed",
  "queries": [
    {
      "id": 1,
      "query_text": "climate change",
      "search_engine": "serper",
      "max_results": 20,
      "result_count": 20,
      "status": "completed",
      "results": [
        {
          "id": 1,
          "url": "https://example.edu/climate-change",
          "title": "Understanding Climate Change",
          "description": "A comprehensive guide to climate change...",
          "rank": 1,
          "domain": "example.edu",
          "scraped": false
        }
      ]
    }
  ],
  "created_at": "2025-01-15T10:30:00"
}
```

### Delete Session

```bash
curl -X DELETE http://localhost:8000/api/search/session/1 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## Scraping API

### Create Scraping Job

**Basic Scraping (Depth 1):**
```bash
curl -X POST http://localhost:8000/api/scraping/jobs \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 1,
    "name": "Basic Content Scraping",
    "depth": 1,
    "domain_filter": "same_domain",
    "delay_min": 2.0,
    "delay_max": 5.0,
    "respect_robots_txt": true
  }'
```

**Multi-level Scraping with Domain Filter:**
```bash
curl -X POST http://localhost:8000/api/scraping/jobs \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 1,
    "name": "Deep Academic Scraping",
    "depth": 3,
    "domain_filter": "allow_tld_list",
    "allowed_tlds": [".edu", ".org", ".gov"],
    "delay_min": 3.0,
    "delay_max": 7.0,
    "max_retries": 3,
    "timeout": 30,
    "respect_robots_txt": true
  }'
```

**Response:**
```json
{
  "id": 1,
  "session_id": 1,
  "name": "Basic Content Scraping",
  "status": "pending",
  "depth": 1,
  "created_at": "2025-01-15T11:00:00"
}
```

### Start Scraping Job

```bash
curl -X POST http://localhost:8000/api/scraping/jobs/1/start \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Get Job Status and Progress

```bash
curl -X GET http://localhost:8000/api/scraping/jobs/1 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Response:**
```json
{
  "id": 1,
  "name": "Basic Content Scraping",
  "status": "processing",
  "depth": 1,
  "current_depth": 1,
  "total_urls": 45,
  "urls_scraped": 23,
  "urls_failed": 2,
  "urls_skipped": 5,
  "progress_percentage": 51.1,
  "started_at": "2025-01-15T11:01:00",
  "domain_filter": "same_domain",
  "delay_min": 2.0,
  "delay_max": 5.0
}
```

### Get Job Statistics

```bash
curl -X GET http://localhost:8000/api/scraping/jobs/1/statistics \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Response:**
```json
{
  "job_id": 1,
  "status": "completed",
  "total_urls": 45,
  "urls_scraped": 40,
  "urls_failed": 3,
  "urls_skipped": 2,
  "success_rate": 88.9,
  "average_scrape_time": 2.3,
  "total_duration": 320,
  "content_by_language": {
    "en": 35,
    "da": 5
  },
  "total_words": 125000,
  "average_words_per_page": 3125
}
```

### Get Scraped Content

```bash
curl -X GET "http://localhost:8000/api/scraping/jobs/1/content?page=1&per_page=10" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Response:**
```json
{
  "content": [
    {
      "id": 1,
      "url": "https://example.edu/article1",
      "title": "Climate Change Overview",
      "language": "en",
      "word_count": 3500,
      "scraped_at": "2025-01-15T11:05:00",
      "status": "success"
    }
  ],
  "total": 40,
  "page": 1,
  "per_page": 10
}
```

### Cancel Running Job

```bash
curl -X POST http://localhost:8000/api/scraping/jobs/1/cancel \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Delete Completed Job

```bash
curl -X DELETE http://localhost:8000/api/scraping/jobs/1 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## Analysis API

### Analyze Single Content

```bash
curl -X POST http://localhost:8000/api/analysis/analyze \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "content_ids": [1],
    "extract_nouns": true,
    "extract_entities": true,
    "max_nouns": 100,
    "min_frequency": 2
  }'
```

**Response:**
```json
{
  "results": [
    {
      "content_id": 1,
      "language": "en",
      "noun_count": 87,
      "entity_count": 23,
      "analyzed_at": "2025-01-15T12:00:00"
    }
  ]
}
```

### Batch Analysis

```bash
curl -X POST http://localhost:8000/api/analysis/batch \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "content_ids": [1, 2, 3, 4, 5],
    "extract_nouns": true,
    "extract_entities": true,
    "max_nouns": 50,
    "background": true
  }'
```

**Response (background task):**
```json
{
  "task_id": "abc123...",
  "status": "processing",
  "message": "Batch analysis started in background"
}
```

### Analyze Entire Scraping Job

```bash
curl -X POST http://localhost:8000/api/analysis/job/1 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "extract_nouns": true,
    "extract_entities": true
  }'
```

### Get Analysis Results

```bash
curl -X GET http://localhost:8000/api/analysis/content/1 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Response:**
```json
{
  "content_id": 1,
  "language": "en",
  "analyzed_at": "2025-01-15T12:00:00",
  "nouns": [
    {
      "word": "climate",
      "lemma": "climate",
      "frequency": 15,
      "tfidf_score": 0.87,
      "positions": [12, 45, 89, 156, 234, 301, 405, 512, 634, 789, 901, 1023, 1156, 1234, 1401]
    },
    {
      "word": "change",
      "lemma": "change",
      "frequency": 18,
      "tfidf_score": 0.82,
      "positions": [18, 52, 95, 162, 240, 307, 411, 518, 640, 795, 907, 1029, 1162, 1240, 1407, 1501, 1623, 1745]
    }
  ],
  "entities": [
    {
      "text": "United Nations",
      "label": "ORG",
      "start_pos": 450,
      "end_pos": 464,
      "confidence": 0.95
    },
    {
      "text": "Paris Agreement",
      "label": "EVENT",
      "start_pos": 890,
      "end_pos": 905,
      "confidence": 0.92
    },
    {
      "text": "Copenhagen",
      "label": "GPE",
      "start_pos": 1234,
      "end_pos": 1244,
      "confidence": 0.98
    }
  ]
}
```

### Get Extracted Nouns Only

```bash
curl -X GET http://localhost:8000/api/analysis/content/1/nouns \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Get Extracted Entities Only

```bash
curl -X GET http://localhost:8000/api/analysis/content/1/entities \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Get Job-Level Aggregates

```bash
curl -X GET http://localhost:8000/api/analysis/job/1/aggregate \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Response:**
```json
{
  "job_id": 1,
  "total_content_analyzed": 40,
  "languages": {
    "en": 35,
    "da": 5
  },
  "top_nouns": [
    {
      "word": "climate",
      "total_frequency": 450,
      "avg_tfidf": 0.85,
      "document_count": 38
    },
    {
      "word": "change",
      "total_frequency": 430,
      "avg_tfidf": 0.82,
      "document_count": 37
    }
  ],
  "top_entities": [
    {
      "text": "United Nations",
      "label": "ORG",
      "frequency": 25,
      "document_count": 20
    },
    {
      "text": "Paris Agreement",
      "label": "EVENT",
      "frequency": 18,
      "document_count": 15
    }
  ],
  "entity_type_distribution": {
    "ORG": 45,
    "GPE": 38,
    "PERSON": 22,
    "DATE": 67,
    "EVENT": 12
  }
}
```

### Delete Analysis Results

```bash
curl -X DELETE http://localhost:8000/api/analysis/content/1 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## Admin API

### Create New User (Admin Only)

```bash
curl -X POST http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "researcher",
    "email": "researcher@example.com",
    "password": "securepass123",
    "is_admin": false
  }'
```

### List All Users (Admin Only)

```bash
curl -X GET http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### Update User (Admin Only)

```bash
curl -X PUT http://localhost:8000/api/admin/users/2 \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newemail@example.com",
    "is_active": true
  }'
```

### Delete User (Admin Only)

```bash
curl -X DELETE http://localhost:8000/api/admin/users/2 \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

---

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 202 | Accepted | Request accepted for processing |
| 204 | No Content | Successful deletion |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong",
  "error_code": "SPECIFIC_ERROR_CODE",
  "field_errors": {
    "field_name": ["Error message for this field"]
  }
}
```

### Example Error Responses

**Authentication Error (401):**
```json
{
  "detail": "Invalid authentication credentials"
}
```

**Validation Error (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "max_results"],
      "msg": "ensure this value is less than or equal to 100",
      "type": "value_error.number.not_le"
    }
  ]
}
```

**Not Found (404):**
```json
{
  "detail": "Search session not found"
}
```

---

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **General API**: 100 requests/minute
- **Search**: 10 requests/minute
- **Scraping**: 5 requests/minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1641024000
```

---

## Best Practices

### 1. Store Tokens Securely
- Never commit tokens to version control
- Use environment variables for tokens
- Refresh tokens before expiration

### 2. Handle Errors Gracefully
- Always check HTTP status codes
- Implement retry logic with exponential backoff
- Log errors for debugging

### 3. Use Pagination
- Always paginate large result sets
- Use reasonable page sizes (10-50)
- Cache results when appropriate

### 4. Batch Operations
- Use batch endpoints for multiple items
- Prefer background processing for large jobs
- Poll for status updates appropriately

### 5. Respect Rate Limits
- Implement client-side rate limiting
- Use exponential backoff on 429 errors
- Consider caching frequently accessed data

---

## Interactive API Documentation

For interactive API testing and complete schema documentation, visit:

**http://localhost:8000/docs** (Swagger UI)
**http://localhost:8000/redoc** (ReDoc)

These provide:
- Interactive API testing
- Complete request/response schemas
- Authentication testing
- Example values
- Response codes and descriptions

---

## Need Help?

- **Full Documentation**: [docs/INDEX.md](INDEX.md)
- **Project Status**: [docs/PROJECT_STATUS.md](PROJECT_STATUS.md)
- **Feature Guides**: See [docs/INDEX.md](INDEX.md) for specific guides
