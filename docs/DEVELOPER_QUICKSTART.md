# Developer Quickstart Guide

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 18+ (for frontend tooling)
- Docker & Docker Compose (optional but recommended)

## Quick Setup with Docker

```bash
# Clone the repository
git clone https://github.com/your-org/issue-observatory-search.git
cd issue-observatory-search

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys and configuration

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head

# Create admin user
docker-compose exec backend python scripts/create_admin.py

# Access the application
# Frontend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Manual Setup

### 1. Database Setup

```bash
# Create PostgreSQL database
createdb issue_observatory

# Install pgvector extension (for embeddings)
psql -d issue_observatory -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 2. Redis Setup

```bash
# Install Redis (Ubuntu/Debian)
sudo apt-get install redis-server

# Start Redis
redis-server
```

### 3. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install playwright browsers
playwright install chromium

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost/issue_observatory"
export REDIS_URL="redis://localhost:6379"
export SECRET_KEY="your-secret-key-here"
export GOOGLE_API_KEY="your-google-api-key"
export SERP_API_KEY="your-serp-api-key"

# Run migrations
alembic upgrade head

# Start Celery worker (in separate terminal)
celery -A backend.tasks worker --loglevel=info

# Start Celery beat (for scheduled tasks, in another terminal)
celery -A backend.tasks beat --loglevel=info

# Start backend server
uvicorn backend.main:app --reload --port 8000
```

### 4. Frontend Setup

```bash
# No build step needed for HTMX + Alpine.js
# Frontend is served directly by FastAPI
# Access at http://localhost:8000
```

## Project Structure

```
issue_observatory_search/
├── backend/
│   ├── api/              # API endpoints
│   ├── core/             # Business logic
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Service layer
│   ├── tasks/            # Celery tasks
│   ├── utils/            # Utilities
│   ├── config.py         # Configuration
│   └── main.py           # FastAPI app
├── frontend/
│   ├── static/           # CSS/JS/Images
│   └── templates/        # HTML templates
├── migrations/           # Alembic migrations
├── tests/                # Test suite
├── scripts/              # Utility scripts
└── docker/               # Docker configurations
```

## Key Development Commands

### Database Operations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Reset database
alembic downgrade base && alembic upgrade head
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Run specific test file
pytest tests/test_search.py

# Run integration tests only
pytest -m integration
```

### Code Quality

```bash
# Format code with Black
black backend/

# Sort imports
isort backend/

# Type checking
mypy backend/

# Linting
flake8 backend/
```

## Common Development Tasks

### Adding a New Search Engine

1. Create new file in `backend/core/search_engines/`:

```python
# backend/core/search_engines/new_engine.py
from .base import SearchEngineBase

class NewEngine(SearchEngineBase):
    async def search(self, query: str, max_results: int, **kwargs):
        # Implementation
        pass
```

2. Register in `backend/core/search_engines/__init__.py`:

```python
SEARCH_ENGINES = {
    "google_custom": GoogleCustomSearch,
    "serp_api": SerpApiSearch,
    "new_engine": NewEngine,  # Add here
}
```

### Adding a New Network Builder

1. Create new file in `backend/core/network/builders/`:

```python
# backend/core/network/builders/new_builder.py
from .base import NetworkBuilderBase

class NewNetworkBuilder(NetworkBuilderBase):
    async def build(self, data, config):
        # Implementation
        pass
```

2. Register in `backend/services/network_service.py`:

```python
NETWORK_BUILDERS = {
    "search_website": SearchWebsiteBuilder,
    "website_noun": WebsiteNounBuilder,
    "website_concept": WebsiteConceptBuilder,
    "new_type": NewNetworkBuilder,  # Add here
}
```

### Creating API Endpoints

```python
# backend/api/new_endpoint.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/new", tags=["new"])

@router.post("/action")
async def new_action(
    data: RequestSchema,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Implementation
    return ResponseSchema(...)
```

Register in `backend/main.py`:

```python
from .api import new_endpoint

app.include_router(new_endpoint.router)
```

### Adding Celery Tasks

```python
# backend/tasks/new_task.py
from celery import current_app as celery_app

@celery_app.task(bind=True)
def new_long_running_task(self, param1, param2):
    # Update progress
    self.update_state(
        state='PROGRESS',
        meta={'current': 50, 'total': 100}
    )
    # Implementation
    return result
```

## Environment Variables

Create `.env` file:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/issue_observatory

# Redis
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Search APIs
GOOGLE_API_KEY=your-google-api-key
GOOGLE_CSE_ID=your-custom-search-engine-id
SERP_API_KEY=your-serp-api-key

# Scraping
PLAYWRIGHT_TIMEOUT=30000
SCRAPE_DELAY=2
MAX_CONCURRENT_SCRAPES=5

# NLP Models
SPACY_MODEL=da_core_news_sm
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2

# Frontend
FRONTEND_URL=http://localhost:8000

# Development
DEBUG=True
RELOAD=True
LOG_LEVEL=INFO
```

## API Testing with curl

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Save token
TOKEN="your-jwt-token"

# Execute search
curl -X POST http://localhost:8000/api/search/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "Test Search",
    "queries": ["renewable energy denmark"],
    "search_engine": "google_custom",
    "max_results": 10
  }'

# Check task status
curl -X GET http://localhost:8000/api/search/status/task-id \
  -H "Authorization: Bearer $TOKEN"
```

## Debugging Tips

1. **Enable SQL logging**:
```python
# In config.py
SQLALCHEMY_ECHO = True
```

2. **Celery debugging**:
```bash
# Run with debug logging
celery -A backend.tasks worker --loglevel=debug
```

3. **FastAPI interactive docs**:
   - Visit http://localhost:8000/docs for Swagger UI
   - Visit http://localhost:8000/redoc for ReDoc

4. **Database inspection**:
```bash
# Connect to database
psql -d issue_observatory

# List tables
\dt

# Describe table
\d+ search_sessions
```

## Production Considerations

1. **Use production ASGI server**:
```bash
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

2. **Enable HTTPS** with Let's Encrypt

3. **Set up monitoring** with Prometheus/Grafana

4. **Configure log aggregation** with ELK stack

5. **Implement rate limiting** with Redis

6. **Use connection pooling** for database

7. **Set up backup strategy** for PostgreSQL

## Troubleshooting

### Common Issues

1. **Playwright installation fails**:
```bash
# Install system dependencies
sudo apt-get install libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0
playwright install-deps chromium
```

2. **Database connection errors**:
```bash
# Check PostgreSQL is running
systemctl status postgresql

# Check connection
psql -U postgres -h localhost
```

3. **Celery tasks not executing**:
```bash
# Check Redis is running
redis-cli ping

# Check Celery workers
celery -A backend.tasks inspect active
```

## Getting Help

- Check the `/docs` folder for detailed documentation
- Review the test files for usage examples
- Open an issue on GitHub for bugs
- Join our Discord for community support

## Next Steps

1. Read the [API Specification](./API_SPECIFICATION.md)
2. Review the [Database Schema](./DATABASE_SCHEMA.md)
3. Check the [Project Specification](./PROJECT_SPECIFICATION.md)
4. Start with simple searches and gradually explore features
5. Contribute improvements back to the project!
