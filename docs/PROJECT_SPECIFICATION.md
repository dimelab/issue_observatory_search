# Issue Observatory Search - Project Specification

## Project Overview

Issue Observatory Search is a web application that enables users to map issues and relationships through web searches and content analysis. The system allows users to search for websites using keywords, scrape content from those websites, and generate network graphs showing relationships between search terms, websites, and extracted concepts.

## Core Features

### 1. Search & Scraping Module
- Multi-keyword web searches using configurable search engines
- Intelligent deduplication to avoid redundant scraping
- Multi-level scraping depth configuration
- Domain filtering capabilities
- Asynchronous task processing for scalability

### 2. Content Analysis Module
- Text extraction and cleaning
- Noun extraction with TF-IDF weighting
- Named Entity Recognition (NER)
- LLM-based concept extraction
- Multi-language support with focus on Danish

### 3. Network Generation Module
- Search-to-website networks with ranking weights
- Website-to-noun bipartite networks
- Website-to-concept knowledge graphs
- Graph backboning for pruning
- GEXF export format

### 4. User Management
- User authentication and authorization
- Data isolation between users
- Admin-managed user creation
- Session management

## Technical Architecture

### Backend Stack
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy 2.0
- **Task Queue**: Celery + Redis
- **Web Scraping**: Playwright
- **NLP**: spaCy, NLTK
- **Embeddings**: sentence-transformers
- **Network Analysis**: NetworkX

### Frontend Stack
- **Framework**: HTMX + Alpine.js
- **CSS**: Tailwind CSS
- **Charts/Visualization**: D3.js (optional)

### Search Engine Integrations
1. Google Custom Search API
2. SERP API
3. Extensible interface for additional engines

## Data Models

### Core Entities
1. **User**: Authentication and ownership
2. **SearchSession**: Groups related searches
3. **SearchQuery**: Individual search terms
4. **SearchResult**: Links from search engines
5. **Website**: Unique scraped websites
6. **WebsiteContent**: Scraped text content with timestamps
7. **ExtractedNoun**: Nouns with TF-IDF scores
8. **ExtractedConcept**: LLM-derived concepts
9. **NetworkExport**: Generated network files

## API Endpoints

### Authentication
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### Search Operations
- `POST /api/search/execute`
- `GET /api/search/sessions`
- `GET /api/search/session/{id}`
- `DELETE /api/search/session/{id}`

### Scraping Operations
- `POST /api/scrape/websites`
- `POST /api/scrape/manual`
- `GET /api/scrape/status/{task_id}`

### Network Generation
- `POST /api/network/generate`
- `GET /api/network/exports`
- `GET /api/network/download/{id}`

### Admin Operations
- `POST /api/admin/users`
- `GET /api/admin/users`
- `DELETE /api/admin/users/{id}`

## Configuration Parameters

### Search Configuration
- `search_engine`: "google_custom" | "serp_api"
- `max_results`: 1-200 (per search term)
- `allowed_domains`: List of TLDs (e.g., [".dk", ".de", ".com"])

### Scraping Configuration
- `scrape_depth`: 1 | 2 | 3
  - Level 1: Scrape only returned URLs
  - Level 2: Scrape + N additional same-domain URLs
  - Level 3: Exhaustive same-domain scraping
- `max_urls_per_domain`: Integer (for Level 2)
- `recollect`: Boolean (force re-scraping)

### Network Configuration
- `network_type`: "search_website" | "website_noun" | "website_concept"
- `languages`: List of ISO codes (e.g., ["da", "en"])
- `top_n_nouns`: Integer or float < 1 (proportion)
- `backbone_percentage`: Float (for concept networks)

## Security Considerations
- JWT-based authentication
- Rate limiting on API endpoints
- Input validation and sanitization
- SQL injection prevention via ORM
- XSS protection
- CSRF tokens for forms

## Scalability Features
- Asynchronous task processing
- Database connection pooling
- Caching layer (Redis)
- Horizontal scaling support
- Batch processing capabilities

## Development Guidelines
- Modular architecture for easy extension
- Dependency injection pattern
- Comprehensive error handling
- Logging and monitoring
- Unit and integration tests
- API documentation via OpenAPI

## Deployment
- Docker containerization
- Environment-based configuration
- Database migrations via Alembic
- CI/CD pipeline support
- Production/staging/development environments
