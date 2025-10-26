# Database Schema - Issue Observatory Search

## Overview
PostgreSQL database with SQLAlchemy ORM. All tables include `created_at` and `updated_at` timestamps.

## Tables

### users
User accounts for authentication and data ownership.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Unique user identifier |
| username | VARCHAR(50) | UNIQUE, NOT NULL | Login username |
| email | VARCHAR(255) | UNIQUE, NOT NULL | User email address |
| password_hash | VARCHAR(255) | NOT NULL | Bcrypt hashed password |
| is_admin | BOOLEAN | DEFAULT FALSE | Admin privileges flag |
| is_active | BOOLEAN | DEFAULT TRUE | Account active status |
| last_login | TIMESTAMP | NULL | Last login timestamp |
| created_at | TIMESTAMP | NOT NULL | Account creation time |
| updated_at | TIMESTAMP | NOT NULL | Last modification time |

**Indexes:**
- `idx_users_username` on (username)
- `idx_users_email` on (email)

### search_sessions
Groups related search queries together.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Session identifier |
| user_id | INTEGER | FOREIGN KEY → users(id), NOT NULL | Owner of the session |
| name | VARCHAR(255) | NOT NULL | Session name |
| description | TEXT | NULL | Optional description |
| status | VARCHAR(20) | DEFAULT 'pending' | pending/processing/completed/failed |
| config | JSON | NULL | Session configuration |
| started_at | TIMESTAMP | NULL | Processing start time |
| completed_at | TIMESTAMP | NULL | Processing end time |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| updated_at | TIMESTAMP | NOT NULL | Last modification time |

**Indexes:**
- `idx_search_sessions_user_id` on (user_id)
- `idx_search_sessions_status` on (status)
- `idx_search_sessions_created_at` on (created_at)

### search_queries
Individual search terms within a session.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Query identifier |
| session_id | INTEGER | FOREIGN KEY → search_sessions(id), NOT NULL | Parent session |
| query_text | VARCHAR(500) | NOT NULL | Search query string |
| search_engine | VARCHAR(50) | NOT NULL | Engine used (google_custom/serp_api) |
| max_results | INTEGER | NOT NULL | Maximum results requested |
| allowed_domains | JSON | NULL | Domain filter list |
| status | VARCHAR(20) | DEFAULT 'pending' | Query execution status |
| result_count | INTEGER | DEFAULT 0 | Actual results returned |
| error_message | TEXT | NULL | Error details if failed |
| executed_at | TIMESTAMP | NULL | Execution timestamp |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| updated_at | TIMESTAMP | NOT NULL | Last modification time |

**Indexes:**
- `idx_search_queries_session_id` on (session_id)
- `idx_search_queries_status` on (status)

### search_results
Links returned from search engines.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Result identifier |
| query_id | INTEGER | FOREIGN KEY → search_queries(id), NOT NULL | Parent query |
| url | TEXT | NOT NULL | Result URL |
| title | VARCHAR(500) | NULL | Page title |
| description | TEXT | NULL | Snippet/description |
| rank | INTEGER | NOT NULL | Position in search results |
| domain | VARCHAR(255) | NOT NULL | Extracted domain |
| scraped | BOOLEAN | DEFAULT FALSE | Has been scraped |
| created_at | TIMESTAMP | NOT NULL | Creation time |

**Indexes:**
- `idx_search_results_query_id` on (query_id)
- `idx_search_results_url_hash` on (MD5(url))
- `idx_search_results_domain` on (domain)

### websites
Unique websites discovered through searches or manual input.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Website identifier |
| url | TEXT | UNIQUE, NOT NULL | Canonical URL |
| domain | VARCHAR(255) | NOT NULL | Domain name |
| title | VARCHAR(500) | NULL | Website title |
| last_scraped_at | TIMESTAMP | NULL | Last scraping time |
| scrape_count | INTEGER | DEFAULT 0 | Times scraped |
| robots_txt | TEXT | NULL | Cached robots.txt |
| sitemap_url | TEXT | NULL | Sitemap URL if found |
| created_at | TIMESTAMP | NOT NULL | First discovery time |
| updated_at | TIMESTAMP | NOT NULL | Last modification time |

**Indexes:**
- `idx_websites_url_hash` on (MD5(url))
- `idx_websites_domain` on (domain)

### website_content
Scraped content from websites with versioning.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Content identifier |
| website_id | INTEGER | FOREIGN KEY → websites(id), NOT NULL | Parent website |
| user_id | INTEGER | FOREIGN KEY → users(id), NOT NULL | User who scraped |
| url | TEXT | NOT NULL | Specific page URL |
| raw_html | TEXT | NULL | Original HTML (compressed) |
| extracted_text | TEXT | NULL | Clean extracted text |
| language | VARCHAR(10) | NULL | Detected language code |
| word_count | INTEGER | DEFAULT 0 | Word count |
| scrape_depth | INTEGER | NOT NULL | Depth level (1/2/3) |
| status | VARCHAR(20) | NOT NULL | success/failed/timeout |
| error_message | TEXT | NULL | Error details if failed |
| scraped_at | TIMESTAMP | NOT NULL | Scraping timestamp |
| created_at | TIMESTAMP | NOT NULL | Creation time |

**Indexes:**
- `idx_website_content_website_id` on (website_id)
- `idx_website_content_user_id` on (user_id)
- `idx_website_content_scraped_at` on (scraped_at)
- `idx_website_content_language` on (language)

### extracted_nouns
Nouns extracted from website content.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Noun identifier |
| content_id | INTEGER | FOREIGN KEY → website_content(id), NOT NULL | Source content |
| text | VARCHAR(255) | NOT NULL | Noun text |
| lemma | VARCHAR(255) | NOT NULL | Lemmatized form |
| count | INTEGER | NOT NULL | Occurrence count |
| tfidf_score | FLOAT | NULL | TF-IDF score |
| language | VARCHAR(10) | NOT NULL | Language code |
| created_at | TIMESTAMP | NOT NULL | Extraction time |

**Indexes:**
- `idx_extracted_nouns_content_id` on (content_id)
- `idx_extracted_nouns_lemma` on (lemma)
- `idx_extracted_nouns_tfidf` on (tfidf_score DESC)

### extracted_entities
Named entities extracted from content.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Entity identifier |
| content_id | INTEGER | FOREIGN KEY → website_content(id), NOT NULL | Source content |
| text | VARCHAR(255) | NOT NULL | Entity text |
| type | VARCHAR(50) | NOT NULL | Entity type (PERSON/ORG/LOC/etc) |
| count | INTEGER | NOT NULL | Occurrence count |
| confidence | FLOAT | NULL | Extraction confidence |
| created_at | TIMESTAMP | NOT NULL | Extraction time |

**Indexes:**
- `idx_extracted_entities_content_id` on (content_id)
- `idx_extracted_entities_type` on (type)
- `idx_extracted_entities_text` on (text)

### extracted_concepts
LLM-derived concepts from content.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Concept identifier |
| content_id | INTEGER | FOREIGN KEY → website_content(id), NOT NULL | Source content |
| concept | VARCHAR(500) | NOT NULL | Concept description |
| embedding | VECTOR(768) | NULL | Sentence embedding |
| relevance_score | FLOAT | NOT NULL | Relevance/confidence score |
| cluster_id | INTEGER | NULL | Concept cluster ID |
| created_at | TIMESTAMP | NOT NULL | Extraction time |

**Indexes:**
- `idx_extracted_concepts_content_id` on (content_id)
- `idx_extracted_concepts_cluster` on (cluster_id)
- `idx_extracted_concepts_embedding` using ivfflat on (embedding)

### network_exports
Generated network graphs.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Network identifier |
| user_id | INTEGER | FOREIGN KEY → users(id), NOT NULL | Owner |
| name | VARCHAR(255) | NOT NULL | Network name |
| type | VARCHAR(50) | NOT NULL | Network type |
| config | JSON | NOT NULL | Generation configuration |
| node_count | INTEGER | NOT NULL | Number of nodes |
| edge_count | INTEGER | NOT NULL | Number of edges |
| file_path | TEXT | NOT NULL | Storage path |
| file_size | INTEGER | NOT NULL | File size in bytes |
| metadata | JSON | NULL | Additional metadata |
| created_at | TIMESTAMP | NOT NULL | Generation time |

**Indexes:**
- `idx_network_exports_user_id` on (user_id)
- `idx_network_exports_type` on (type)
- `idx_network_exports_created_at` on (created_at)

### network_sessions
Many-to-many relationship between networks and search sessions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| network_id | INTEGER | FOREIGN KEY → network_exports(id) | Network ID |
| session_id | INTEGER | FOREIGN KEY → search_sessions(id) | Session ID |

**Primary Key:** (network_id, session_id)

### celery_tasks
Track background task execution.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(255) | PRIMARY KEY | Celery task ID |
| user_id | INTEGER | FOREIGN KEY → users(id), NOT NULL | Task owner |
| task_type | VARCHAR(50) | NOT NULL | Task type |
| status | VARCHAR(20) | NOT NULL | Task status |
| progress | JSON | NULL | Progress information |
| result | JSON | NULL | Task result |
| error | TEXT | NULL | Error message |
| started_at | TIMESTAMP | NULL | Start time |
| completed_at | TIMESTAMP | NULL | Completion time |
| created_at | TIMESTAMP | NOT NULL | Queue time |

**Indexes:**
- `idx_celery_tasks_user_id` on (user_id)
- `idx_celery_tasks_status` on (status)
- `idx_celery_tasks_type` on (task_type)

### api_keys
Store external API keys per user (optional).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Key identifier |
| user_id | INTEGER | FOREIGN KEY → users(id), NOT NULL | Owner |
| service | VARCHAR(50) | NOT NULL | Service name |
| key_hash | VARCHAR(255) | NOT NULL | Encrypted API key |
| is_active | BOOLEAN | DEFAULT TRUE | Key status |
| last_used | TIMESTAMP | NULL | Last usage time |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| expires_at | TIMESTAMP | NULL | Expiration time |

**Indexes:**
- `idx_api_keys_user_service` on (user_id, service)

## Relationships

```
users
  ├── search_sessions (1:N)
  ├── website_content (1:N)
  ├── network_exports (1:N)
  ├── celery_tasks (1:N)
  └── api_keys (1:N)

search_sessions
  ├── search_queries (1:N)
  └── network_sessions (N:M with network_exports)

search_queries
  └── search_results (1:N)

websites
  └── website_content (1:N)

website_content
  ├── extracted_nouns (1:N)
  ├── extracted_entities (1:N)
  └── extracted_concepts (1:N)

network_exports
  └── network_sessions (N:M with search_sessions)
```

## Database Views

### v_user_statistics
Aggregated statistics per user.

```sql
CREATE VIEW v_user_statistics AS
SELECT 
    u.id,
    u.username,
    COUNT(DISTINCT ss.id) as session_count,
    COUNT(DISTINCT wc.website_id) as website_count,
    COUNT(DISTINCT ne.id) as network_count,
    MAX(ss.created_at) as last_session_date,
    MAX(wc.scraped_at) as last_scrape_date
FROM users u
LEFT JOIN search_sessions ss ON u.id = ss.user_id
LEFT JOIN website_content wc ON u.id = wc.user_id
LEFT JOIN network_exports ne ON u.id = ne.user_id
GROUP BY u.id, u.username;
```

### v_website_statistics
Statistics about websites.

```sql
CREATE VIEW v_website_statistics AS
SELECT 
    w.id,
    w.domain,
    COUNT(DISTINCT wc.id) as content_versions,
    COUNT(DISTINCT wc.user_id) as unique_users,
    MAX(wc.scraped_at) as last_scraped,
    AVG(wc.word_count) as avg_word_count
FROM websites w
LEFT JOIN website_content wc ON w.id = wc.website_id
GROUP BY w.id, w.domain;
```

## Indexes Strategy

1. **Primary Keys**: All tables have auto-incrementing integer primary keys
2. **Foreign Keys**: All foreign key columns are indexed
3. **Unique Constraints**: On natural keys (username, email, url)
4. **Performance Indexes**: On frequently queried columns (status, created_at, domain)
5. **Full-Text Search**: Consider adding PostgreSQL full-text search on extracted_text
6. **Vector Similarity**: Using pgvector for concept embeddings

## Migration Strategy

Use Alembic for database migrations:

1. Initial migration creates all tables
2. Separate migrations for indexes
3. Migration for views
4. Seed migration for default admin user

## Performance Considerations

1. **Partitioning**: Consider partitioning website_content by scraped_at
2. **Archiving**: Move old data to archive tables after N months
3. **Compression**: Use JSONB compression for large JSON fields
4. **Vacuum**: Regular VACUUM ANALYZE for statistics
5. **Connection Pooling**: Use PgBouncer in production

## Security Considerations

1. **Row-Level Security**: Implement RLS for multi-tenant isolation
2. **Encryption**: Encrypt sensitive data (API keys)
3. **Audit Log**: Consider adding audit table for sensitive operations
4. **Backup**: Daily backups with point-in-time recovery
5. **Read Replicas**: For heavy read operations
