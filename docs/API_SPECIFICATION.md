# API Specification - Issue Observatory Search

## Base URL
```
https://api.issue-observatory.com/v1
```

## Authentication
All authenticated endpoints require a Bearer token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### Authentication Endpoints

#### POST /auth/login
Login with username and password.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response (200 OK):**
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "integer",
    "username": "string",
    "email": "string",
    "is_admin": "boolean"
  }
}
```

#### POST /auth/logout
Logout current user (invalidate token).

**Response (200 OK):**
```json
{
  "message": "Successfully logged out"
}
```

#### GET /auth/me
Get current user information.

**Response (200 OK):**
```json
{
  "id": "integer",
  "username": "string",
  "email": "string",
  "is_admin": "boolean",
  "created_at": "datetime",
  "last_login": "datetime"
}
```

### Search Endpoints

#### POST /search/execute
Execute web searches for multiple keywords.

**Request Body:**
```json
{
  "session_name": "string",
  "queries": ["keyword1", "keyword2"],
  "search_engine": "google_custom" | "serp_api",
  "max_results": 10,
  "allowed_domains": [".dk", ".com"],
  "auto_scrape": true,
  "scrape_config": {
    "depth": 1 | 2 | 3,
    "max_urls_per_domain": 10,
    "recollect": false
  }
}
```

**Response (202 Accepted):**
```json
{
  "session_id": "integer",
  "task_id": "string",
  "status": "pending",
  "message": "Search task queued",
  "status_url": "/search/status/{task_id}"
}
```

#### GET /search/sessions
Get all search sessions for current user.

**Query Parameters:**
- `page`: integer (default: 1)
- `per_page`: integer (default: 20)
- `sort`: "created_at" | "updated_at" (default: "created_at")
- `order`: "asc" | "desc" (default: "desc")

**Response (200 OK):**
```json
{
  "sessions": [
    {
      "id": "integer",
      "name": "string",
      "created_at": "datetime",
      "updated_at": "datetime",
      "query_count": "integer",
      "website_count": "integer",
      "status": "pending" | "processing" | "completed" | "failed"
    }
  ],
  "total": "integer",
  "page": "integer",
  "per_page": "integer",
  "pages": "integer"
}
```

#### GET /search/session/{id}
Get detailed information about a search session.

**Response (200 OK):**
```json
{
  "id": "integer",
  "name": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "status": "string",
  "queries": [
    {
      "id": "integer",
      "query": "string",
      "search_engine": "string",
      "max_results": "integer",
      "result_count": "integer",
      "status": "string"
    }
  ],
  "results": [
    {
      "id": "integer",
      "url": "string",
      "title": "string",
      "description": "string",
      "rank": "integer",
      "query_id": "integer",
      "scraped": "boolean"
    }
  ]
}
```

#### DELETE /search/session/{id}
Delete a search session and all related data.

**Response (204 No Content)**

### Scraping Endpoints

#### POST /scrape/websites
Scrape websites from search results or manual input.

**Request Body:**
```json
{
  "source": "search_session" | "manual",
  "session_id": "integer",  // if source is search_session
  "urls": ["string"],       // if source is manual
  "config": {
    "depth": 1 | 2 | 3,
    "max_urls_per_domain": 10,
    "recollect": false,
    "timeout": 30,
    "wait_time": 2
  }
}
```

**Response (202 Accepted):**
```json
{
  "task_id": "string",
  "website_count": "integer",
  "status": "pending",
  "status_url": "/scrape/status/{task_id}"
}
```

#### GET /scrape/status/{task_id}
Get status of a scraping task.

**Response (200 OK):**
```json
{
  "task_id": "string",
  "status": "pending" | "processing" | "completed" | "failed",
  "progress": {
    "total": "integer",
    "completed": "integer",
    "failed": "integer"
  },
  "results": [
    {
      "url": "string",
      "status": "success" | "failed",
      "pages_scraped": "integer",
      "error": "string"  // if failed
    }
  ],
  "started_at": "datetime",
  "completed_at": "datetime"
}
```

#### POST /scrape/upload-csv
Upload a CSV file with URLs to scrape.

**Request Body (multipart/form-data):**
- `file`: CSV file
- `config`: JSON string with scrape configuration

**Response (200 OK):**
```json
{
  "urls_count": "integer",
  "valid_urls": ["string"],
  "invalid_urls": ["string"],
  "task_id": "string"
}
```

### Network Generation Endpoints

#### POST /network/generate
Generate a network graph from scraped data.

**Request Body:**
```json
{
  "name": "string",
  "type": "search_website" | "website_noun" | "website_concept",
  "session_ids": ["integer"],
  "config": {
    // For search_website network
    "use_rank_weights": true,
    
    // For website_noun network
    "languages": ["da", "en"],
    "top_n_nouns": 10,  // or 0.1 for proportion
    "use_tfidf": true,
    "include_ner": false,
    
    // For website_concept network
    "languages": ["da"],
    "backbone_percentage": 0.15,
    "embedding_model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "min_similarity": 0.7
  }
}
```

**Response (202 Accepted):**
```json
{
  "network_id": "integer",
  "task_id": "string",
  "status": "pending",
  "status_url": "/network/status/{task_id}"
}
```

#### GET /network/exports
Get all network exports for current user.

**Query Parameters:**
- `page`: integer
- `per_page`: integer
- `type`: "search_website" | "website_noun" | "website_concept"

**Response (200 OK):**
```json
{
  "networks": [
    {
      "id": "integer",
      "name": "string",
      "type": "string",
      "created_at": "datetime",
      "node_count": "integer",
      "edge_count": "integer",
      "file_size": "integer",
      "download_url": "/network/download/{id}"
    }
  ],
  "total": "integer",
  "page": "integer",
  "per_page": "integer"
}
```

#### GET /network/download/{id}
Download a network file in GEXF format.

**Response (200 OK):**
- Content-Type: application/gexf+xml
- Content-Disposition: attachment; filename="network_{id}.gexf"
- Body: GEXF XML data

#### GET /network/status/{task_id}
Get status of network generation task.

**Response (200 OK):**
```json
{
  "task_id": "string",
  "status": "pending" | "processing" | "completed" | "failed",
  "progress": {
    "phase": "string",
    "percentage": "integer"
  },
  "result": {
    "network_id": "integer",
    "node_count": "integer",
    "edge_count": "integer",
    "download_url": "string"
  },
  "error": "string"  // if failed
}
```

### Analysis Endpoints

#### POST /analysis/extract-nouns
Extract nouns from scraped content.

**Request Body:**
```json
{
  "website_ids": ["integer"],
  "languages": ["da", "en"],
  "use_tfidf": true,
  "top_n": 100
}
```

**Response (200 OK):**
```json
{
  "results": [
    {
      "website_id": "integer",
      "url": "string",
      "nouns": [
        {
          "text": "string",
          "count": "integer",
          "tfidf_score": "float"
        }
      ]
    }
  ]
}
```

#### POST /analysis/extract-entities
Extract named entities from scraped content.

**Request Body:**
```json
{
  "website_ids": ["integer"],
  "languages": ["da", "en"],
  "entity_types": ["PERSON", "ORG", "LOC"]
}
```

**Response (200 OK):**
```json
{
  "results": [
    {
      "website_id": "integer",
      "url": "string",
      "entities": [
        {
          "text": "string",
          "type": "string",
          "count": "integer"
        }
      ]
    }
  ]
}
```

### Admin Endpoints

#### POST /admin/users
Create a new user (admin only).

**Request Body:**
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "is_admin": false
}
```

**Response (201 Created):**
```json
{
  "id": "integer",
  "username": "string",
  "email": "string",
  "is_admin": "boolean",
  "created_at": "datetime"
}
```

#### GET /admin/users
Get all users (admin only).

**Response (200 OK):**
```json
{
  "users": [
    {
      "id": "integer",
      "username": "string",
      "email": "string",
      "is_admin": "boolean",
      "created_at": "datetime",
      "last_login": "datetime",
      "session_count": "integer",
      "website_count": "integer"
    }
  ]
}
```

#### DELETE /admin/users/{id}
Delete a user and all their data (admin only).

**Response (204 No Content)**

#### GET /admin/stats
Get system statistics (admin only).

**Response (200 OK):**
```json
{
  "users": {
    "total": "integer",
    "active_today": "integer",
    "active_week": "integer"
  },
  "searches": {
    "total": "integer",
    "today": "integer",
    "week": "integer"
  },
  "websites": {
    "total": "integer",
    "unique": "integer",
    "scraped_today": "integer"
  },
  "networks": {
    "total": "integer",
    "by_type": {
      "search_website": "integer",
      "website_noun": "integer",
      "website_concept": "integer"
    }
  },
  "tasks": {
    "pending": "integer",
    "processing": "integer",
    "completed_today": "integer",
    "failed_today": "integer"
  }
}
```

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}  // optional
  }
}
```

### Common Error Codes:
- `UNAUTHORIZED`: Missing or invalid authentication
- `FORBIDDEN`: Insufficient permissions
- `NOT_FOUND`: Resource not found
- `VALIDATION_ERROR`: Invalid request data
- `RATE_LIMITED`: Too many requests
- `TASK_FAILED`: Background task failed
- `SERVER_ERROR`: Internal server error

## Rate Limiting

- Default: 100 requests per minute per user
- Search operations: 10 per minute
- Scraping operations: 5 per minute
- Network generation: 5 per minute

Rate limit headers:
- `X-RateLimit-Limit`: Maximum requests
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Reset timestamp

## Webhooks (Optional)

Users can register webhooks for task completion:

```json
{
  "url": "https://example.com/webhook",
  "events": ["search.completed", "scrape.completed", "network.completed"],
  "secret": "string"
}
```

Webhook payload:
```json
{
  "event": "string",
  "timestamp": "datetime",
  "data": {
    "task_id": "string",
    "status": "string",
    "result": {}
  },
  "signature": "string"  // HMAC-SHA256
}
```
