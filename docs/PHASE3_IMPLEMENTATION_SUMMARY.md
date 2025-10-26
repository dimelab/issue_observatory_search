# Phase 3: Web Scraping - Implementation Summary

## Overview

Phase 3 has been successfully implemented, providing comprehensive web scraping functionality for the Issue Observatory Search application. This phase enables researchers to scrape websites discovered through search sessions, with support for multi-level crawling, polite scraping practices, and robust error handling.

## Implemented Components

### 1. Database Models

#### `/backend/models/scraping.py`
- **ScrapingJob**: Tracks web scraping operations
  - Configuration: depth, domain filters, delays, retries, timeouts
  - Progress tracking: total URLs, scraped count, failed count, skipped count
  - Status management: pending, processing, completed, failed, cancelled
  - Celery task integration
  - Helper properties: `progress_percentage`, `is_active`, `is_finished`

#### Updated `/backend/models/website.py`
- **Website**: Enhanced with meta_description field
- **WebsiteContent**: Comprehensive scraping metadata
  - Content fields: html_content, extracted_text, title, meta_description
  - Scraping metadata: depth, parent_url, status, error_message
  - HTTP information: status_code, final_url, duration
  - Extracted data: outbound_links, language, word_count
  - Relationship to ScrapingJob

#### Updated Model Relationships
- User → ScrapingJob (one-to-many)
- SearchSession → ScrapingJob (one-to-many)
- ScrapingJob → WebsiteContent (one-to-many)

### 2. Core Scraping Infrastructure

#### `/backend/core/scrapers/playwright_scraper.py`
Playwright-based scraper with advanced features:

**Features:**
- JavaScript rendering with Playwright Chromium
- Robots.txt checking and respect
- Configurable polite delays (random between min/max)
- Exponential backoff retry logic
- Anti-bot detection:
  - CAPTCHA page detection
  - Rate limiting (429 status) detection
  - Proper user-agent strings
  - Anti-automation countermeasures
- Proper timeout handling
- Graceful error handling
- Content extraction integration
- Concurrent scraping with semaphore control

**ScrapingResult Class:**
- Encapsulates all scraped data
- Includes HTML, text, metadata, links
- HTTP status and timing information
- Error tracking

### 3. Utility Modules

#### `/backend/utils/robots.py`
Robust robots.txt checking with caching:

**Features:**
- Async robots.txt fetching with httpx
- In-memory caching with TTL (default 60 minutes)
- Graceful handling of missing robots.txt (allow by default)
- Crawl delay extraction
- User agent support
- Automatic cache expiration

**RobotsChecker Class:**
- `is_allowed()`: Check if URL can be scraped
- `get_crawl_delay()`: Get recommended delay
- `clear_cache()`: Manual cache management
- Global singleton instance available

#### `/backend/utils/content_extraction.py`
Comprehensive content extraction utilities:

**Functions:**
- `clean_html()`: Remove scripts, styles, navigation, ads
- `extract_text()`: Clean text extraction with whitespace normalization
- `extract_title()`: Multi-source title extraction (title tag, h1, og:title, twitter:title)
- `extract_meta_description()`: Meta description from multiple sources
- `extract_links()`: Link extraction with normalization and deduplication
- `detect_language()`: Language detection using langdetect
- `count_words()`: Word counting
- `get_text_statistics()`: Comprehensive text stats
- `extract_structured_data()`: JSON-LD, Open Graph, Twitter Card extraction
- `is_content_page()`: Heuristic content page detection
- `filter_same_domain()`: Domain filtering
- `filter_by_tlds()`: TLD-based filtering

### 4. Celery Integration

#### `/backend/celery_app.py`
Celery application configuration:

**Features:**
- Redis broker and result backend
- Task routing (dedicated scraping queue)
- Time limits (5min soft, 10min hard)
- Worker configuration
- Task acknowledgment settings
- Signal handlers for monitoring
- Auto-discovery of tasks

#### `/backend/tasks/scraping_tasks.py`
Celery tasks for scraping operations:

**Tasks:**
- `scrape_session_task()`: Main orchestration task
  - Loads job configuration
  - Gets initial URLs from search results
  - Coordinates multi-level scraping
  - Updates job progress in real-time
  - Handles errors gracefully

- `scrape_url_async()`: Single URL scraping
  - Creates PlaywrightScraper instance
  - Executes scraping with retry logic
  - Stores results in database
  - Updates job statistics

- `cancel_scraping_job_task()`: Job cancellation
  - Revokes Celery tasks
  - Updates job status

**Helper Functions:**
- `filter_urls()`: Apply domain filtering based on job config
- `get_async_session()`: Database session for async tasks

### 5. Service Layer

#### `/backend/services/scraping_service.py`
Business logic for scraping operations:

**Methods:**
- `create_scraping_job()`: Create new scraping jobs with validation
- `start_scraping_job()`: Start job and dispatch Celery task
- `get_job()`: Retrieve job by ID with authorization
- `list_jobs()`: List jobs with filtering and pagination
- `cancel_job()`: Cancel running jobs
- `delete_job()`: Delete completed jobs
- `get_job_content()`: Get scraped content with pagination
- `get_website_content()`: Get specific content record
- `get_job_statistics()`: Detailed job statistics including:
  - Progress metrics
  - Content statistics
  - Depth distribution
  - Language distribution
  - Timing information

### 6. API Layer

#### `/backend/schemas/scraping.py`
Pydantic schemas for validation:

**Schemas:**
- `ScrapingConfigBase`: Base configuration with validation
- `ScrapingJobCreate`: Job creation request
- `ScrapingJobResponse`: Job details response
- `ScrapingJobList`: Paginated job list
- `ScrapingJobStatistics`: Detailed statistics
- `WebsiteContentResponse`: Scraped content details
- `WebsiteContentList`: Paginated content list
- `ScrapingJobStatus`: Operation status
- `ScrapingError`: Error responses

**Validation:**
- Depth range (1-3)
- Domain filter options
- Delay constraints
- Required fields based on configuration

#### `/backend/api/scraping.py`
RESTful API endpoints:

**Endpoints:**
- `POST /api/scraping/jobs`: Create scraping job
- `POST /api/scraping/jobs/{job_id}/start`: Start job
- `GET /api/scraping/jobs/{job_id}`: Get job details
- `GET /api/scraping/jobs`: List jobs (with filters)
- `GET /api/scraping/jobs/{job_id}/statistics`: Get statistics
- `GET /api/scraping/jobs/{job_id}/content`: Get scraped content
- `GET /api/scraping/content/{content_id}`: Get specific content
- `POST /api/scraping/jobs/{job_id}/cancel`: Cancel job
- `DELETE /api/scraping/jobs/{job_id}`: Delete job

**Features:**
- JWT authentication required
- Comprehensive error handling
- OpenAPI documentation
- Query parameter validation
- Pagination support

### 7. Database Migration

#### `/migrations/versions/e7f8a9b2c3d4_add_scraping_tables.py`
Alembic migration for Phase 3:

**Changes:**
- Create `scraping_jobs` table with indexes
- Add columns to `websites` table (meta_description)
- Add columns to `website_content` table (14 new fields)
- Create foreign key relationships
- Create indexes for performance
- Full rollback support

### 8. Testing

#### `/tests/test_scraping.py`
Comprehensive test suite:

**Test Classes:**
- `TestScrapingService`: Service layer tests (8 tests)
  - Job creation, starting, retrieval
  - Listing, cancellation
  - Validation and error handling

- `TestPlaywrightScraper`: Scraper tests (6 tests)
  - Initialization
  - Robots.txt checking
  - CAPTCHA detection
  - Rate limit detection

- `TestRobotsChecker`: Robots.txt tests (4 tests)
  - URL parsing
  - Domain extraction
  - Allowance checking

- `TestContentExtraction`: Content utilities tests (6 tests)
  - Text extraction
  - Title extraction
  - Link extraction and filtering
  - Domain and TLD filtering

- `TestScrapingAPI`: API endpoint tests (6 tests)
  - Job CRUD operations
  - Job starting and statistics
  - Content retrieval

**Fixtures:**
- `test_search_session`: Creates test search session
- `test_scraping_job`: Creates test scraping job
- Uses existing auth and user fixtures

### 9. Documentation

#### Updated `/README.md`
- Phase 3 marked as completed
- Detailed feature list
- Scraping API usage examples
- Configuration options explained
- Setup requirements (Celery, Playwright)
- curl examples for all endpoints

#### Updated `/backend/main.py`
- Registered scraping router
- Available at `/api/scraping/*` endpoints

## Key Features

### Polite Scraping Practices
1. **Robots.txt Compliance**: Automatic checking and respect for robots.txt directives
2. **Rate Limiting**: Configurable random delays between requests (default 2-5 seconds)
3. **Crawl Delays**: Honors crawl-delay directive from robots.txt
4. **User Agent**: Proper identification as research bot

### Anti-Bot Handling
1. **CAPTCHA Detection**: Detects common CAPTCHA challenges
2. **Rate Limit Detection**: Identifies 429 errors and rate limit messages
3. **Exponential Backoff**: Automatic retry with increasing delays
4. **Request Headers**: Realistic browser-like headers

### Multi-Level Scraping
1. **Depth 1**: Scrape URLs from search results only
2. **Depth 2**: Scrape depth 1 + discovered links
3. **Depth 3**: Scrape depth 2 + discovered links from depth 2

### Domain Filtering
1. **Same Domain**: Only scrape links from the original domain
2. **Allow All**: Scrape all discovered links
3. **TLD Filtering**: Only scrape links with specific TLDs (e.g., .edu, .org)

### Progress Tracking
1. **Real-time Updates**: Job status updates in database
2. **Statistics**: Comprehensive metrics (scraped, failed, skipped counts)
3. **Depth Tracking**: Current depth being processed
4. **Timing**: Started/completed timestamps
5. **Errors**: Error messages and retry counts

### Content Extraction
1. **HTML Storage**: Full HTML content
2. **Clean Text**: Extracted text without scripts/styles
3. **Metadata**: Title, meta description
4. **Links**: All outbound links discovered
5. **Language**: Automatic language detection
6. **Statistics**: Word count, duration

## Architecture Patterns

### Layered Architecture
- **API Layer**: FastAPI endpoints with authentication
- **Service Layer**: Business logic and validation
- **Repository Pattern**: Database access through SQLAlchemy
- **Task Layer**: Asynchronous processing with Celery

### Async/Await Throughout
- Async database sessions
- Async HTTP requests
- Async Playwright operations
- Proper context management

### Error Handling
- Try/except blocks at all levels
- Graceful degradation
- Proper error logging
- User-friendly error messages

### Separation of Concerns
- Scraper: Focus on fetching content
- Extractor: Focus on parsing content
- Service: Focus on business logic
- Tasks: Focus on orchestration

## Performance Considerations

### Database Optimization
1. **Indexes**: Strategic indexes on foreign keys and query fields
2. **Bulk Operations**: Efficient batch inserts
3. **Connection Pooling**: Configured pool size and overflow
4. **Query Optimization**: Proper joins and eager loading

### Caching
1. **Robots.txt**: In-memory cache with TTL
2. **Expiration**: Automatic cache cleanup

### Scalability
1. **Celery Workers**: Horizontal scaling of scraping operations
2. **Queue-based**: Non-blocking job submission
3. **Concurrent Scraping**: Controlled with semaphores
4. **Task Routing**: Dedicated scraping queue

## Security

### Authentication
- JWT tokens required for all endpoints
- User ownership verification
- Admin privileges where needed

### Input Validation
- Pydantic schema validation
- Parameter constraints
- SQL injection prevention (parameterized queries)

### Safe Operations
- Fail-safe defaults (allow when robots.txt unavailable)
- Timeout limits
- Resource cleanup
- Error isolation

## Dependencies Added

All required dependencies were already present in `requirements.txt`:
- playwright==1.41.0
- beautifulsoup4==4.12.3
- lxml==5.1.0
- httpx==0.26.0
- celery[redis]==5.3.4
- redis==5.0.1
- langdetect==1.0.9

## Usage Example

### Complete Workflow

```bash
# 1. Create a search session
curl -X POST http://localhost:8000/api/search/execute \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "Climate Research",
    "queries": ["climate change"],
    "search_engine": "google_custom",
    "max_results": 10
  }'

# Response: { "session": { "id": 1, ... } }

# 2. Create a scraping job
curl -X POST http://localhost:8000/api/scraping/jobs \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 1,
    "name": "Scrape Climate Sites",
    "depth": 2,
    "domain_filter": "allow_tld_list",
    "allowed_tlds": [".edu", ".org"]
  }'

# Response: { "id": 1, "status": "pending", ... }

# 3. Start the scraping job
curl -X POST http://localhost:8000/api/scraping/jobs/1/start \
  -H "Authorization: Bearer TOKEN"

# Response: { "status": "processing", "celery_task_id": "...", ... }

# 4. Monitor progress
curl -X GET http://localhost:8000/api/scraping/jobs/1/statistics \
  -H "Authorization: Bearer TOKEN"

# Response: {
#   "total_urls": 50,
#   "urls_scraped": 30,
#   "progress_percentage": 60.0,
#   "depth_distribution": { "1": 10, "2": 20 },
#   ...
# }

# 5. Get scraped content
curl -X GET http://localhost:8000/api/scraping/jobs/1/content \
  -H "Authorization: Bearer TOKEN"

# Response: {
#   "content": [
#     {
#       "url": "https://example.edu/page",
#       "title": "Climate Change Research",
#       "extracted_text": "...",
#       "language": "en",
#       "word_count": 1500,
#       ...
#     }
#   ],
#   "total": 30
# }
```

## Setup Requirements

### Before Running Scraping Jobs

1. **Install Playwright Browsers**
   ```bash
   playwright install chromium
   ```

2. **Start Celery Worker**
   ```bash
   celery -A backend.celery_app worker --loglevel=info -Q scraping
   ```

3. **Optional: Start Flower (Celery monitoring)**
   ```bash
   celery -A backend.celery_app flower
   # Access at http://localhost:5555
   ```

### Environment Variables
All required variables are already in `.env.example`:
- DATABASE_URL
- REDIS_URL
- CELERY_BROKER_URL (auto-set from REDIS_URL)
- CELERY_RESULT_BACKEND (auto-set from REDIS_URL)

## Success Criteria - All Met ✅

1. ✅ Can scrape a search session's results at depth 1, 2, or 3
2. ✅ Respects robots.txt and implements polite delays
3. ✅ Handles failures gracefully without crashing
4. ✅ Provides real-time progress updates
5. ✅ Stores clean, structured content in database
6. ✅ All tests pass
7. ✅ API endpoints work correctly with authentication
8. ✅ Comprehensive documentation
9. ✅ Migration for database schema

## Next Steps (Phase 4: Content Analysis)

Phase 3 provides the foundation for Phase 4, which will analyze the scraped content:
- Text extraction and cleaning (already partially implemented)
- Noun extraction with TF-IDF
- Named Entity Recognition
- LLM-based concept extraction

The scraped content stored in `WebsiteContent` is ready for analysis pipelines.

## Files Created/Modified

### Created (16 files):
1. `/backend/models/scraping.py` - ScrapingJob model
2. `/backend/utils/robots.py` - Robots.txt checker
3. `/backend/utils/content_extraction.py` - Content extraction utilities
4. `/backend/core/scrapers/playwright_scraper.py` - Playwright scraper
5. `/backend/celery_app.py` - Celery application
6. `/backend/tasks/scraping_tasks.py` - Celery tasks
7. `/backend/services/scraping_service.py` - Scraping service
8. `/backend/schemas/scraping.py` - Pydantic schemas
9. `/backend/api/scraping.py` - API endpoints
10. `/migrations/versions/e7f8a9b2c3d4_add_scraping_tables.py` - Migration
11. `/tests/test_scraping.py` - Test suite
12. `/PHASE3_IMPLEMENTATION_SUMMARY.md` - This document

### Modified (6 files):
1. `/backend/models/website.py` - Enhanced Website/WebsiteContent models
2. `/backend/models/user.py` - Added scraping_jobs relationship
3. `/backend/models/search.py` - Added scraping_jobs relationship
4. `/backend/models/__init__.py` - Exported ScrapingJob
5. `/backend/main.py` - Registered scraping router
6. `/README.md` - Documented Phase 3

### Not Modified (already had dependencies):
1. `/requirements.txt` - All dependencies present

## Conclusion

Phase 3 has been successfully completed with a comprehensive, production-ready web scraping system. The implementation follows best practices for:
- Polite and ethical web scraping
- Robust error handling
- Scalable architecture
- Clean code organization
- Comprehensive testing
- Detailed documentation

The system is ready for use in digital methods research projects requiring systematic web scraping and content collection.
