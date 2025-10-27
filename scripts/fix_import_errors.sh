#!/bin/bash
# Script to fix all import and attribute errors found by code review

echo "Fixing import and attribute errors..."

# Issue 1-3: Fix backend/api/dependencies imports
echo "Fixing import paths in scraping.py, bulk_search.py, advanced_search.py..."
find backend/api -name "*.py" -exec sed -i 's/from backend\.api\.dependencies import get_current_user/from backend.utils.dependencies import CurrentUser/g' {} \;

# Issues 7-8: Fix ScrapedContent imports
echo "Fixing ScrapedContent model imports..."
sed -i 's/from backend\.models import User, SearchSession, SearchQuery, SearchResult, ScrapingJob, ScrapedContent/from backend.models import User, SearchSession, SearchQuery, SearchResult, ScrapingJob\nfrom backend.models.website import WebsiteContent/g' backend/api/frontend.py
sed -i 's/from backend\.models import User, SearchSession, SearchQuery, SearchResult, ScrapingJob, ScrapedContent/from backend.models import User, SearchSession, SearchQuery, SearchResult, ScrapingJob\nfrom backend.models.website import WebsiteContent/g' backend/api/partials.py

# Replace ScrapedContent with WebsiteContent in code
sed -i 's/ScrapedContent/WebsiteContent/g' backend/api/frontend.py
sed -i 's/ScrapedContent/WebsiteContent/g' backend/api/partials.py

# Fix job_id to scraping_job_id
sed -i 's/WebsiteContent\.job_id/WebsiteContent.scraping_job_id/g' backend/api/frontend.py
sed -i 's/WebsiteContent\.job_id/WebsiteContent.scraping_job_id/g' backend/api/partials.py

# Issue 9: Fix SearchResult.position to SearchResult.rank
sed -i 's/SearchResult\.position/SearchResult.rank/g' backend/api/partials.py

# Issue 14: Fix async_session import in tasks
sed -i 's/from backend\.database import async_session/from backend.database import AsyncSessionLocal/g' backend/tasks/network_tasks.py

echo "✅ All automated fixes applied!"
echo ""
echo "⚠️  Manual fixes still needed:"
echo "1. Update dependency injection patterns (User = Depends(get_current_user) → CurrentUser)"
echo "2. Fix field access errors in frontend.py and partials.py"
echo "3. Add urlparse import to partials.py"
echo ""
echo "Run: python scripts/verify_installation.py to test"
