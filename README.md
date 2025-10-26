# Issue Observatory Search

A comprehensive web application for digital methods research: conduct systematic web searches, scrape and analyze content, and generate network graphs showing relationships between search terms, websites, and concepts.

**Status**: Production Ready | **Version**: 5.0.0 | [Full Documentation](docs/INDEX.md) | [Security Audit](docs/SECURITY_AUDIT.md) | [Production Checklist](docs/PRODUCTION_CHECKLIST.md)

## Features

✅ **Multi-Engine Search** - Google Custom Search, Serper API & SERP API
✅ **Advanced Search** - Query snowballing, multi-perspective search, temporal analysis
✅ **Intelligent Web Scraping** - Multi-level scraping with robots.txt compliance
✅ **NLP Analysis** - Noun extraction, Named Entity Recognition, TF-IDF ranking
✅ **Network Generation** - Issue networks with statistical backboning (GEXF export)
✅ **Interactive Visualization** - Vis.js network viewer with search and filtering
✅ **Modern Web UI** - HTMX + Alpine.js + Tailwind CSS responsive interface
✅ **Keyboard Shortcuts** - 25+ shortcuts for power users
✅ **Accessibility** - WCAG 2.1 AA compliant, screen reader support
✅ **Background Processing** - Celery task queue for long-running operations
✅ **RESTful API** - Comprehensive API with authentication
✅ **Production Ready** - Security audit, monitoring, CI/CD, comprehensive testing
✅ **OWASP Compliant** - All Top 10 2021 vulnerabilities addressed

📖 [View Complete Feature List](docs/PROJECT_STATUS.md)

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and start all services
git clone <repository-url>
cd issue_observatory_search
docker-compose up -d

# Access the application
open http://localhost:8000
```

### Option 2: Local Development

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Install NLP models
python scripts/install_nlp_models.py

# 3. Install browser for scraping
playwright install chromium

# 4. Configure environment
cp .env.example .env
# Edit .env with your configuration

# 5. Run database migrations
alembic upgrade head

# 6. Start services
docker-compose up -d postgres redis  # Or start manually

# 7. Start Celery workers
celery -A backend.celery_app worker -Q scraping --loglevel=info &
celery -A backend.celery_app worker -Q analysis --loglevel=info &

# 8. Start application
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Access at: **http://localhost:8000**
API docs: **http://localhost:8000/docs**

---

## Configuration

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/issue_observatory

# Redis
REDIS_URL=redis://localhost:6379/0

# Security (change in production!)
SECRET_KEY=your-secret-key-min-32-chars

# Search Engine (choose one or both)
SERPER_API_KEY=your_serper_key          # Recommended: $2/1k searches
GOOGLE_CUSTOM_SEARCH_API_KEY=your_key    # Alternative: $5/1k searches
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your_id
```

📝 See [`.env.example`](.env.example) for all configuration options.

### Search Engine Setup

**Serper (Recommended)**
- Cost: ~$2 per 1,000 searches
- Sign up: https://serper.dev
- No additional setup required

**Google Custom Search**
- Cost: Free 100/day, then $5 per 1,000
- Requires Google Cloud account
- [Setup Guide](https://developers.google.com/custom-search)

📖 [Detailed Comparison](docs/SERPER_INTEGRATION.md)

---

## Basic Usage

### Using the Web Interface

1. **Login** at http://localhost:8000
2. **Create Search Session** - Enter keywords, choose search engine
3. **View Results** - Browse discovered websites
4. **Start Scraping** - Configure depth and filters
5. **Analyze Content** - Extract nouns and entities

### Using the API

**Authentication**
```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

**Execute Search**
```bash
curl -X POST http://localhost:8000/api/search/execute \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "Climate Research",
    "queries": ["climate change", "global warming"],
    "search_engine": "serper",
    "max_results": 20
  }'
```

**Start Scraping**
```bash
curl -X POST http://localhost:8000/api/scraping/jobs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 1,
    "name": "Content Scraping",
    "depth": 2,
    "domain_filter": "same_domain"
  }'
```

**Analyze Content**
```bash
curl -X POST http://localhost:8000/api/analysis/batch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content_ids": [1, 2, 3],
    "extract_nouns": true,
    "extract_entities": true
  }'
```

**Generate Network**
```bash
curl -X POST http://localhost:8000/api/networks/generate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Climate Network",
    "type": "search_website",
    "session_ids": [1, 2, 3],
    "backboning": {"enabled": true, "alpha": 0.05}
  }'
```

📖 [Complete API Guide](docs/API_SPECIFICATION.md) | [Network Generation Guide](docs/NETWORK_GENERATION_GUIDE.md)

---

## Documentation

### Essential Guides
- 🎉 [**Project Complete**](docs/PROJECT_COMPLETE.md) - ⭐ **Full project summary (v4.0.0)**
- 📘 [**Project Status**](docs/PROJECT_STATUS.md) - Current implementation status
- 📗 [**API Reference**](docs/API_SPECIFICATION.md) - Complete API documentation
- 📙 [**Database Schema**](docs/DATABASE_SCHEMA.md) - Database design
- 📕 [**Documentation Index**](docs/INDEX.md) - All documentation

### Feature Guides
- 🔍 [Search Integration](docs/SERPER_INTEGRATION.md)
- 🔬 [Advanced Search](docs/ADVANCED_SEARCH_GUIDE.md) - Query snowballing, templates, temporal
- 📖 [Query Formulation](docs/QUERY_FORMULATION_STRATEGIES.md) - Digital methods strategies
- 🕷️ [Web Scraping](docs/PHASE3_COMPLETION_SUMMARY.md)
- 🧠 [NLP Analysis](docs/PHASE4_ANALYSIS_GUIDE.md)
- 🕸️ [Network Generation](docs/NETWORK_GENERATION_GUIDE.md)
- 🎨 [Frontend Interface](docs/FRONTEND_COMPLETION_SUMMARY.md)
- ⚡ [Performance Optimization](docs/PERFORMANCE.md)
- 💾 [Backup & Restore](docs/DATA_PERSISTENCE_GUIDE.md)
- 🔒 [Security Audit](docs/SECURITY_AUDIT.md)
- 📊 [Monitoring Guide](docs/MONITORING_GUIDE.md)
- 🚀 [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)

### Developer Guides
- 🚀 [Quick Start](docs/DEVELOPER_QUICKSTART.md)
- 🏗️ [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP.md)
- 📚 [Quick Reference](docs/QUICK_REFERENCE.md)

---

## Requirements

- **Python**: 3.11 or higher
- **PostgreSQL**: 14 or higher
- **Redis**: 7 or higher
- **RAM**: 4GB minimum
- **Disk**: 10GB minimum (for models and data)

**Optional Dependencies**:
- `graph-tool` - Advanced graph algorithms (requires system install, see `requirements-optional.txt`)
- GPU support for PyTorch (for faster NLP processing)

---

## Technology Stack

**Backend**
- FastAPI - Async web framework
- SQLAlchemy 2.0 - Async ORM
- Celery - Background tasks
- spaCy - NLP processing
- Playwright - Web scraping

**Frontend**
- HTMX - Dynamic interactions
- Tailwind CSS - Styling
- Jinja2 - Templating

**Infrastructure**
- PostgreSQL - Database
- Redis - Cache & queue
- Docker - Containerization

---

## Project Status

| Phase | Status | Features |
|-------|--------|----------|
| Phase 1: Foundation | ✅ Complete | Auth, Users, Database |
| Phase 2: Search | ✅ Complete | Google, Serper, SERP API, Deduplication |
| Phase 3: Scraping | ✅ Complete | Multi-level, Polite, Async |
| Phase 4: Analysis | ✅ Complete | NLP, TF-IDF, NER |
| Phase 5: Networks | ✅ Complete | Graph generation, Backboning, GEXF export |
| Phase 7: Advanced Search | ✅ Complete | Query snowballing, Templates, Temporal, Bulk |
| Phase 8: Advanced UI | ✅ Complete | Network viz, Components, Shortcuts, A11y |
| Phase 9: Performance | ✅ Complete | Caching, Indexes, Pooling, Rate limiting |
| Phase 10: Production | ✅ Complete | Security audit, Monitoring, CI/CD, Testing |
| Frontend | ✅ Complete | Responsive UI, Real-time updates |

**Overall**: 100% Complete (9/9 phases) - Production Ready, Secure & Monitored!

📊 [Detailed Status](docs/PROJECT_STATUS.md)

---

## Development

### Run Tests
```bash
pytest
pytest --cov=backend --cov-report=html  # With coverage
```

### Code Quality
```bash
black .                    # Format code
ruff check . --fix        # Lint and fix
mypy backend              # Type checking
```

### Database Migrations
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

---

## Deployment

### Production Checklist

- [ ] Change `SECRET_KEY` in production
- [ ] Set `DEBUG=false`
- [ ] Configure proper `DATABASE_URL`
- [ ] Set up Redis with persistence
- [ ] Configure CORS origins
- [ ] Set up HTTPS/SSL
- [ ] Configure rate limiting
- [ ] Set up monitoring and logging
- [ ] Configure backups
- [ ] Review security settings

📖 [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) *(coming soon)*

---

## Support

- **Documentation**: [docs/INDEX.md](docs/INDEX.md)
- **API Reference**: http://localhost:8000/docs (when running)
- **Issues**: GitHub Issues
- **Questions**: GitHub Discussions

---

## Contributing

Contributions are welcome! Please:

1. Read the [Project Specification](docs/PROJECT_SPECIFICATION.md)
2. Review [Agent Prompts](docs/AGENT_PROMPTS.md) for coding standards
3. Write tests for new features
4. Follow existing code style
5. Update documentation

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Acknowledgments

Built with assistance from:
- **backend-architect** agent - Backend implementation
- **frontend-developer** agent - UI implementation
- **digital-methods-specialist** agent - Research methodology

---

**Ready to start?** → Run `docker-compose up -d` and visit http://localhost:8000
