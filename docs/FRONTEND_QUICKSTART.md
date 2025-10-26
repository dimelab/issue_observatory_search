# Frontend Quick Start Guide

Get the Issue Observatory Search frontend up and running in minutes.

## Prerequisites

- Python 3.9+
- PostgreSQL database
- API keys for search engines (Google Custom Search or Serper)

## Installation

### 1. Install Dependencies

```bash
cd /Users/jakobbk/Documents/postdoc/codespace/issue_observatory_search

# Create virtual environment (if not exists)
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and set:
# - DATABASE_URL
# - SECRET_KEY
# - GOOGLE_API_KEY or SERPER_API_KEY
```

### 3. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Create admin user (optional)
python -c "
from backend.database import AsyncSessionLocal
from backend.models import User
from backend.utils.auth import get_password_hash
import asyncio

async def create_admin():
    async with AsyncSessionLocal() as db:
        admin = User(
            username='admin',
            email='admin@example.com',
            hashed_password=get_password_hash('admin123'),
            is_admin=True
        )
        db.add(admin)
        await db.commit()

asyncio.run(create_admin())
"
```

### 4. Start the Application

```bash
# Development server with auto-reload
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Or production server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. Access the Application

Open your browser and navigate to:
- **Frontend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## First Login

### Default Credentials
If you created the admin user above:
- **Username**: `admin`
- **Password**: `admin123`

Otherwise, create a user via the API:

```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "researcher",
    "email": "researcher@example.com",
    "password": "securepassword123"
  }'
```

## Quick Tour

### 1. Dashboard
After login, you'll see the dashboard with:
- Welcome message
- Search sessions list (empty initially)
- Quick statistics
- "New Search" button

### 2. Create a Search

Click "New Search" and fill in:
- **Session Name**: e.g., "Climate Change News"
- **Search Engine**: Google or Serper
- **Keywords**: One per line, e.g.:
  ```
  climate change
  global warming
  carbon emissions
  ```
- **Max Results**: 10 (default)
- **Domain Filter**: Optional, e.g., `.edu,.org`

Click "Execute Search" and wait for results.

### 3. View Results

From the dashboard, click "View" on your search session to see:
- Query statistics
- Results per query (collapsible)
- Links to scraped content

### 4. Start Scraping

On the session details page:
1. Click "Start Scraping"
2. Choose scraping depth (1-3)
3. Click "Start Job"

You'll be redirected to the job details page with real-time progress.

### 5. Monitor Scraping

The scraping job page shows:
- Real-time progress bar
- Success/failed counts
- Scraped content list
- Auto-refresh every 3 seconds

## Common Tasks

### Create a New Search Session

1. Dashboard → "New Search"
2. Fill in form
3. Submit
4. View results on session details page

### Delete a Search Session

1. Dashboard → Find session
2. Click "Delete"
3. Confirm deletion

### Cancel a Scraping Job

1. Scraping Jobs → Find job
2. Click "View"
3. Click "Cancel Job" (if running)

### View Scraped Content

1. Scraping Jobs → Find job
2. Click "View"
3. Scroll to "Scraped Content" section
4. Click "Load More" for pagination

## Keyboard Shortcuts

- **Tab**: Navigate between elements
- **Enter**: Activate buttons/links
- **Escape**: Close modals
- **Space**: Toggle checkboxes

## Mobile Access

The interface is fully responsive. Access from any device:
- Mobile phone (320px+)
- Tablet (640px+)
- Desktop (1024px+)

## Troubleshooting

### "Cannot connect to database"

Check your `DATABASE_URL` in `.env`:
```bash
# PostgreSQL example
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
```

### "Invalid credentials"

Reset password via API:
```bash
# Update user password
curl -X PUT "http://localhost:8000/api/admin/users/{user_id}" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "newpassword123"}'
```

### "Search failed"

Check API keys in `.env`:
```bash
# For Google Custom Search
GOOGLE_API_KEY=your_api_key_here
GOOGLE_SEARCH_ENGINE_ID=your_engine_id_here

# OR for Serper
SERPER_API_KEY=your_api_key_here
```

### "Static files not loading"

Ensure the frontend directory exists and has the correct structure:
```bash
ls -la frontend/static/css/
ls -la frontend/static/js/
```

### "Templates not found"

Verify template directory:
```bash
ls -la frontend/templates/
```

### "HTMX not working"

Check browser console for errors. Ensure:
1. HTMX CDN is accessible
2. JWT token is set in localStorage
3. API endpoints are responding

## Development Tips

### Hot Reload

The development server (`--reload`) automatically reloads on file changes:
- Python files: Auto-reload
- Templates: Refresh browser
- Static files: Refresh browser

### Debug Mode

Enable debug mode in `.env`:
```bash
DEBUG=true
```

This will:
- Show detailed error messages
- Enable stack traces
- Log all SQL queries

### Browser DevTools

Use browser DevTools to:
- Inspect HTMX requests (Network tab)
- Check JWT token (Application → Local Storage)
- Debug JavaScript (Console tab)
- Test responsive design (Device toolbar)

## API Integration

### Get Sessions via API

```bash
curl -X GET "http://localhost:8000/api/search/sessions" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Execute Search via API

```bash
curl -X POST "http://localhost:8000/api/search/execute" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "Test Search",
    "search_engine": "google",
    "queries": ["climate change", "global warming"],
    "max_results": 10
  }'
```

### Start Scraping Job via API

```bash
curl -X POST "http://localhost:8000/api/scraping/jobs" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Scraping",
    "session_id": 1,
    "depth": 2
  }'

# Start the job
curl -X POST "http://localhost:8000/api/scraping/jobs/1/start" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Production Deployment

### Using Docker (Recommended)

```bash
# Build image
docker build -t issue-observatory-search .

# Run container
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://..." \
  -e SECRET_KEY="..." \
  -e GOOGLE_API_KEY="..." \
  --name observatory \
  issue-observatory-search
```

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

### Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start with Gunicorn
gunicorn backend.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

## Security Checklist

Before deploying to production:

- [ ] Change default admin password
- [ ] Set strong `SECRET_KEY` in `.env`
- [ ] Enable HTTPS (SSL/TLS certificate)
- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Configure CORS for production domains
- [ ] Enable rate limiting
- [ ] Set up monitoring and logging
- [ ] Regular backups of database
- [ ] Update dependencies regularly

## Next Steps

1. **Explore the API**: Visit `/docs` for interactive API documentation
2. **Read the Documentation**: Check `/frontend/README.md` for detailed info
3. **Customize**: Modify templates and styles to match your needs
4. **Contribute**: Report issues or submit pull requests

## Support

For help:
1. Check the main README: `/README.md`
2. Review implementation docs: `/FRONTEND_IMPLEMENTATION.md`
3. Check API docs: `/docs`
4. Review logs for errors

## License

This project is for academic research purposes.

---

**Congratulations!** You're now ready to use the Issue Observatory Search application.

Happy researching!
