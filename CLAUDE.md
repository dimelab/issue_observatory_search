# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Issue Observatory Search is a web application for scraping websites based on search terms and creating network analyses. It consists of a Flask backend API with SQLite database and a frontend using HTMX and Vanilla JavaScript.

## Key Architecture Components

### Backend Structure
- **Flask Application**: Main app in `app.py` with factory pattern in `app/__init__.py`
- **Database Models**: SQLAlchemy models in `app/models/` (User, Scrape, ScrapedPage, SearchTerms)
- **Services Layer**: Business logic in `app/services/` (search engines, scraping, network analysis)
- **API Endpoints**: RESTful routes in `app/api/` (auth, scraping, network)

### Search Engine Integration
- **Modular Design**: `SearchEngineFactory` creates search engine instances
- **Supported Engines**: Google Custom Search API and SERP API
- **Configuration**: API keys stored in environment variables and JSON files

### Web Scraping System
- **Selenium-based**: Uses Chrome WebDriver with configurable depth levels
- **Three Scraping Levels**:
  - Level 1: Search results only
  - Level 2: + Links from same domain
  - Level 3: + All accessible domain links
- **Domain filtering**: Configurable allowed domains list

### Network Analysis
- **Bipartite Networks**: Websites and nouns as nodes, TF-IDF weighted edges
- **Language Support**: spaCy models for multiple languages (Danish default)
- **Export Format**: GEXF files for network visualization

## Common Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Create database tables
python app.py

# Create a user (admin only)
python create_user.py username email password
```

### Running the Application
```bash
# Development server
python app.py

# Production server (with gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Database Operations
```bash
# Flask shell for database operations
flask shell

# In shell: Create all tables
>>> db.create_all()

# In shell: Query users
>>> User.query.all()
```

## Configuration

### Environment Variables
- Copy `config/.env.example` to `config/.env`
- Required variables:
  - `SECRET_KEY`: Flask secret key
  - `MAIN_PATH`: Data directory path
  - `CUSTOMSEARCH`: Path to Google Custom Search API keys JSON
  - `SERP_API_KEY`: SERP API key (optional)

### API Keys Setup
- Google Custom Search: Create `keys/customsearch_keys.json` with format:
  ```json
  {"tokens": [{"key": "API_KEY", "cx": "CX_ID"}]}
  ```
- SERP API: Set `SERP_API_KEY` environment variable

## Frontend Architecture

### HTMX Integration
- Progressive enhancement with HTMX for dynamic content
- Form submissions and page updates without full page reloads
- Real-time scrape status updates

### Template Structure
- Base template with Bootstrap 5 styling
- Modular templates for different sections
- JavaScript enhancements in `static/js/app.js`

## Development Workflow

### Adding New Search Engines
1. Create new class inheriting from `SearchEngineBase` in `app/services/search_engines.py`
2. Implement `search()` method
3. Add to `SearchEngineFactory.create_search_engine()`
4. Update frontend form options

### Adding New Network Types
1. Create new method in `NetworkAnalyzer` class
2. Add network type selection to frontend
3. Update API endpoint to handle new type

### Database Schema Changes
1. Modify models in `app/models/`
2. Create migration script or recreate database
3. Update API endpoints and templates accordingly

## File Structure
- `app/`: Main application package
  - `models/`: Database models
  - `services/`: Business logic services
  - `api/`: API endpoints
  - `templates/`: Jinja2 templates
  - `static/`: CSS, JS, and other static files
- `config/`: Configuration files
- `keys/`: API key files (not committed)
- `data/`: Scraped data storage
- `gexfs/`: Generated network files

## Testing and Debugging

### Manual Testing
- Use browser developer tools for frontend debugging
- Check Flask logs for backend errors
- Test API endpoints with curl or Postman

### Common Issues
- Chrome WebDriver issues: Update ChromeDriver version
- Database locks: Ensure proper connection handling
- Memory usage: Monitor for large scraping operations