# Installation Guide

Complete step-by-step installation guide for Issue Observatory Search.

---

## Prerequisites

- **Python 3.11+** (check: `python3 --version`)
- **pip** (check: `pip --version`)
- **Docker & Docker Compose** (check: `docker --version`)
- **Git** (check: `git --version`)

---

## Quick Install (5 minutes)

```bash
# 1. Clone repository
git clone <repository-url>
cd issue_observatory_search

# 2. Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install Python dependencies (~500MB download, 2-3 minutes)
pip install -e .[dev]

# 4. Install Playwright browser (~300MB download, 1-2 minutes)
python -m playwright install chromium

# 5. Install NLP models (~200MB download, 1-2 minutes)
python scripts/install_nlp_models.py

# 6. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 7. Start infrastructure (MUST be done before migrations!)
docker-compose up -d postgres redis

# 8. Run migrations (requires database to be running)
python -m alembic upgrade head

# 9. Start application
uvicorn backend.main:app --reload
```

Access at: **http://localhost:8000**

---

## Detailed Installation Steps

### Step 1: Install Python Dependencies

```bash
pip install -e .[dev]
```

**What this does**:
- Installs all Python packages from `requirements.txt`
- Installs the application in "editable" mode (`-e`)
- Includes development tools (pytest, black, ruff, etc.) with `[dev]`

**Expected time**: 2-3 minutes
**Download size**: ~500MB
**Disk space**: ~800MB

**Common issues**:
- ❌ "No matching distribution for X" → Check Python version (must be 3.11+)
- ❌ Pip backtracking → See [Troubleshooting](#troubleshooting) below
- ❌ Permission denied → Use virtual environment or add `--user` flag

---

### Step 2: Install Playwright Browser

```bash
python -m playwright install chromium
```

**What this does**:
- Downloads Chromium browser binary
- **Required** for web scraping functionality
- Playwright Python package was installed in Step 1

**Expected time**: 1-2 minutes
**Download size**: ~300MB
**Disk space**: ~300MB

**Common issues**:
- ❌ "playwright: command not found" → Use `python -m playwright install chromium` instead
- ❌ Permission denied (Linux) → Run `python -m playwright install-deps chromium` first
- ❌ Download fails → Check internet connection, try `python -m playwright install --force chromium`

**Alternative browsers** (optional):
```bash
python -m playwright install firefox  # Firefox
python -m playwright install webkit   # Safari/WebKit
```

---

### Step 3: Install NLP Models

```bash
python scripts/install_nlp_models.py
```

**What this does**:
- Downloads spaCy language models:
  - `en_core_web_sm` - English small model (~40MB)
  - `da_core_news_sm` - Danish small model (~40MB)
- **Required** for content analysis functionality

**Expected time**: 1-2 minutes
**Download size**: ~200MB
**Disk space**: ~200MB

**Common issues**:
- ❌ "Model not found" → Install manually: `python -m spacy download en_core_web_sm`
- ❌ HTTP error → Check internet connection, try again
- ❌ Disk space → Need at least 500MB free

**Alternative models** (better accuracy, slower):
```bash
python -m spacy download en_core_web_md  # Medium (~90MB)
python -m spacy download en_core_web_lg  # Large (~560MB)
```

---

### Step 4: Configure Environment

```bash
cp .env.example .env
nano .env  # or vim, code, etc.
```

**Required settings**:
```bash
# Database (Docker defaults work)
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/issue_observatory

# Redis (Docker defaults work)
REDIS_URL=redis://localhost:6379/0

# Security (CHANGE THIS!)
SECRET_KEY=your-secret-key-min-32-characters-long

# Search API (at least one required)
SERPER_API_KEY=your_serper_key  # Get from https://serper.dev
# OR
GOOGLE_CUSTOM_SEARCH_API_KEY=your_google_key
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your_cse_id
```

**Optional settings**:
```bash
DEBUG=true                    # Enable debug mode
ENVIRONMENT=development       # Environment name
LOG_LEVEL=INFO               # Logging level
```

---

### Step 5: Start Infrastructure Services

```bash
docker-compose up -d postgres redis
```

**What this does**:
- Starts PostgreSQL 16 (database)
- Starts Redis 7 (cache & task queue)
- Runs in background (`-d` = detached)

**Verify services are running**:
```bash
docker ps
# Should show postgres and redis containers

docker-compose logs postgres  # Check database logs
docker-compose logs redis     # Check redis logs
```

**Common issues**:
- ❌ Port already in use → Another service using 5432/6379, stop it or change ports
- ❌ Docker not running → Start Docker Desktop
- ❌ Permission denied → Add user to docker group: `sudo usermod -aG docker $USER`

**Alternative: Install locally** (without Docker):
```bash
# PostgreSQL
sudo apt-get install postgresql-14  # Ubuntu
brew install postgresql@14           # macOS

# Redis
sudo apt-get install redis-server    # Ubuntu
brew install redis                   # macOS
```

---

### Step 6: Run Database Migrations

```bash
python -m alembic upgrade head
```

**What this does**:
- Creates all database tables
- Applies all migrations
- Sets up initial schema

**Verify migrations**:
```bash
python -m alembic current  # Should show latest revision
python -m alembic history  # Show all migrations
```

**Common issues**:
- ❌ "Connection refused" → PostgreSQL not running (see Step 5)
- ❌ "Database does not exist" → Check `DATABASE_URL` in `.env`
- ❌ "ModuleNotFoundError" → Make sure virtual environment is activated
- ❌ Migration fails → Drop database and retry: `python -m alembic downgrade base && python -m alembic upgrade head`

---

### Step 7: Start Celery Workers (Optional)

For background tasks (scraping, analysis):

```bash
# Terminal 1: Scraping worker
celery -A backend.celery_app worker -Q scraping --loglevel=info

# Terminal 2: Analysis worker
celery -A backend.celery_app worker -Q analysis --loglevel=info

# Terminal 3: Beat scheduler (periodic tasks)
celery -A backend.celery_app beat --loglevel=info
```

**Or use tmux/screen**:
```bash
# Start all in background
celery -A backend.celery_app worker -Q scraping --loglevel=info &
celery -A backend.celery_app worker -Q analysis --loglevel=info &
celery -A backend.celery_app beat --loglevel=info &
```

**Monitor with Flower** (optional):
```bash
celery -A backend.celery_app flower --port=5555
# Access at: http://localhost:5555
```

---

### Step 8: Start Application

```bash
# Development (with auto-reload)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Access the application**:
- Web UI: http://localhost:8000
- API Docs: http://localhost:8000/docs
- API ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

---

## Verification

### Test the installation:

```bash
# 1. Check application health
curl http://localhost:8000/health
# Should return: {"status":"healthy"}

# 2. Run tests
pytest tests/

# 3. Check database connection
python -c "from backend.database import engine; print('Database OK')"

# 4. Check Redis connection
python -c "import redis; r=redis.from_url('redis://localhost:6379'); r.ping(); print('Redis OK')"

# 5. Check Playwright
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"

# 6. Check spaCy models
python -c "import spacy; spacy.load('en_core_web_sm'); print('spaCy OK')"
```

All checks should pass without errors.

---

## Total Installation Summary

| Step | Time | Download | Disk Space |
|------|------|----------|------------|
| Python dependencies | 2-3 min | ~500MB | ~800MB |
| Playwright browser | 1-2 min | ~300MB | ~300MB |
| NLP models | 1-2 min | ~200MB | ~200MB |
| Docker images | 2-3 min | ~500MB | ~500MB |
| **Total** | **~8 min** | **~1.5GB** | **~1.8GB** |

**Minimum disk space required**: 2GB free

---

## Troubleshooting

### Dependency Installation Issues

**Problem**: Pip backtracking for a long time
```bash
# Solution 1: Upgrade pip
pip install --upgrade pip setuptools wheel

# Solution 2: Use legacy resolver
pip install -e .[dev] --use-deprecated=legacy-resolver

# Solution 3: Install from requirements.txt directly
pip install -r requirements.txt
```

**Problem**: Conflicting dependencies
```bash
# This should NOT happen with latest requirements.txt
# If it does, check that you have:
pip show celery redis
# celery==5.3.4 and redis==4.6.0 (compatible)
```

### Playwright Issues

**Problem**: "playwright: command not found"
```bash
# Always use Python module syntax
python -m playwright install chromium

# NOT: playwright install chromium (this won't work in venv)
```

**Problem**: Browsers not found after installation
```bash
# Reinstall with force
python -m playwright install --force chromium

# Check installation
python -m playwright --version
```

**Problem**: Linux system dependencies missing
```bash
# Install all dependencies
python -m playwright install-deps

# Or for specific browser
python -m playwright install-deps chromium
```

### Database Issues

**Problem**: Cannot connect to PostgreSQL
```bash
# Check if running
docker ps | grep postgres

# Check logs
docker-compose logs postgres

# Restart
docker-compose restart postgres

# Recreate
docker-compose down
docker-compose up -d postgres
```

**Problem**: Migrations fail
```bash
# Reset database (DANGER: deletes all data!)
python -m alembic downgrade base
python -m alembic upgrade head

# Or start fresh
docker-compose down -v  # Deletes volumes
docker-compose up -d postgres
python -m alembic upgrade head
```

### Port Conflicts

**Problem**: Port 8000 already in use
```bash
# Find what's using it
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Use different port
uvicorn backend.main:app --port 3111
```

**Problem**: PostgreSQL port 5432 in use
```bash
# Option 1: Stop existing PostgreSQL
sudo systemctl stop postgresql  # Linux
brew services stop postgresql   # macOS

# Option 2: Use different port in docker-compose.yml
ports:
  - "5433:5432"  # Host:Container
```

---

## Uninstallation

### Remove application:
```bash
# Stop services
docker-compose down -v  # Removes containers and volumes
celery control shutdown  # Stop workers

# Remove Python packages
pip uninstall issue-observatory-search
pip uninstall -r requirements.txt -y

# Remove Playwright browsers
playwright uninstall chromium

# Remove NLP models
python -m spacy uninstall en_core_web_sm
python -m spacy uninstall da_core_news_sm

# Remove virtual environment
deactivate
rm -rf .venv/
```

**Space freed**: ~2GB

---

## Next Steps

After installation:

1. **Create a user account**: http://localhost:8000/register
2. **Read the Quick Start**: [docs/DEVELOPER_QUICKSTART.md](docs/DEVELOPER_QUICKSTART.md)
3. **Try the API**: http://localhost:8000/docs
4. **Run a search**: [docs/ADVANCED_SEARCH_GUIDE.md](docs/ADVANCED_SEARCH_GUIDE.md)
5. **Explore the docs**: [docs/INDEX.md](docs/INDEX.md)

---

## Getting Help

- **Documentation**: [docs/INDEX.md](docs/INDEX.md)
- **API Reference**: http://localhost:8000/docs (when running)
- **Troubleshooting**: This guide's [Troubleshooting](#troubleshooting) section
- **Issues**: Check GitHub issues or create a new one

---

**Installation complete!** 🎉
