"""Tests for web scraping functionality."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.scraping import ScrapingJob
from backend.models.search import SearchSession, SearchQuery, SearchResult
from backend.models.website import Website, WebsiteContent
from backend.services.scraping_service import ScrapingService
from backend.core.scrapers.playwright_scraper import ScrapingResult, PlaywrightScraper
from backend.utils.robots import RobotsChecker
from backend.utils.content_extraction import (
    extract_text,
    extract_title,
    extract_links,
    filter_same_domain,
    filter_by_tlds,
)


class TestScrapingService:
    """Tests for ScrapingService."""

    @pytest.mark.asyncio
    async def test_create_scraping_job(self, db_session: AsyncSession, test_user, test_search_session):
        """Test creating a scraping job."""
        service = ScrapingService(db_session)

        job = await service.create_scraping_job(
            user_id=test_user.id,
            session_id=test_search_session.id,
            name="Test Scraping Job",
            depth=2,
            domain_filter="same_domain",
            delay_min=1.0,
            delay_max=2.0,
        )

        assert job.id is not None
        assert job.user_id == test_user.id
        assert job.session_id == test_search_session.id
        assert job.name == "Test Scraping Job"
        assert job.depth == 2
        assert job.status == "pending"
        assert job.domain_filter == "same_domain"

    @pytest.mark.asyncio
    async def test_create_job_invalid_session(self, db_session: AsyncSession, test_user):
        """Test creating job with invalid session."""
        service = ScrapingService(db_session)

        with pytest.raises(ValueError, match="Search session not found"):
            await service.create_scraping_job(
                user_id=test_user.id,
                session_id=99999,
                name="Test Job",
            )

    @pytest.mark.asyncio
    async def test_create_job_invalid_depth(self, db_session: AsyncSession, test_user, test_search_session):
        """Test creating job with invalid depth."""
        service = ScrapingService(db_session)

        with pytest.raises(ValueError, match="Depth must be 1, 2, or 3"):
            await service.create_scraping_job(
                user_id=test_user.id,
                session_id=test_search_session.id,
                name="Test Job",
                depth=5,
            )

    @pytest.mark.asyncio
    async def test_start_scraping_job(self, db_session: AsyncSession, test_user, test_search_session):
        """Test starting a scraping job."""
        service = ScrapingService(db_session)

        # Create job
        job = await service.create_scraping_job(
            user_id=test_user.id,
            session_id=test_search_session.id,
            name="Test Job",
        )

        # Mock Celery task
        with patch("backend.services.scraping_service.scrape_session_task") as mock_task:
            mock_task.apply_async.return_value = MagicMock(id="test-task-id")

            # Start job
            started_job = await service.start_scraping_job(job.id, test_user.id)

            assert started_job.status == "processing"
            assert started_job.celery_task_id == "test-task-id"
            assert started_job.started_at is not None
            mock_task.apply_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job(self, db_session: AsyncSession, test_user, test_search_session):
        """Test getting a scraping job."""
        service = ScrapingService(db_session)

        # Create job
        job = await service.create_scraping_job(
            user_id=test_user.id,
            session_id=test_search_session.id,
            name="Test Job",
        )

        # Get job
        retrieved_job = await service.get_job(job.id, test_user.id)

        assert retrieved_job is not None
        assert retrieved_job.id == job.id
        assert retrieved_job.name == "Test Job"

    @pytest.mark.asyncio
    async def test_list_jobs(self, db_session: AsyncSession, test_user, test_search_session):
        """Test listing scraping jobs."""
        service = ScrapingService(db_session)

        # Create multiple jobs
        for i in range(3):
            await service.create_scraping_job(
                user_id=test_user.id,
                session_id=test_search_session.id,
                name=f"Test Job {i}",
            )

        # List jobs
        jobs, total = await service.list_jobs(test_user.id, limit=10, offset=0)

        assert total == 3
        assert len(jobs) == 3
        assert jobs[0].name == "Test Job 2"  # Most recent first

    @pytest.mark.asyncio
    async def test_cancel_job(self, db_session: AsyncSession, test_user, test_search_session):
        """Test cancelling a scraping job."""
        service = ScrapingService(db_session)

        # Create and start job
        job = await service.create_scraping_job(
            user_id=test_user.id,
            session_id=test_search_session.id,
            name="Test Job",
        )

        with patch("backend.services.scraping_service.cancel_scraping_job_task") as mock_task:
            # Cancel job
            cancelled_job = await service.cancel_job(job.id, test_user.id)

            assert cancelled_job is not None
            mock_task.apply_async.assert_called_once()


class TestPlaywrightScraper:
    """Tests for PlaywrightScraper."""

    @pytest.mark.asyncio
    async def test_scraping_result_creation(self):
        """Test creating a ScrapingResult."""
        result = ScrapingResult(
            url="https://example.com",
            status="success",
            title="Example Page",
            extracted_text="This is example text.",
            word_count=4,
        )

        assert result.url == "https://example.com"
        assert result.status == "success"
        assert result.title == "Example Page"
        assert result.word_count == 4

    @pytest.mark.asyncio
    async def test_scraper_initialization(self):
        """Test initializing PlaywrightScraper."""
        scraper = PlaywrightScraper(
            delay_min=1.0,
            delay_max=2.0,
            max_retries=2,
            timeout=15,
        )

        assert scraper.delay_min == 1.0
        assert scraper.delay_max == 2.0
        assert scraper.max_retries == 2
        assert scraper.timeout == 15000  # Converted to milliseconds

    @pytest.mark.asyncio
    async def test_check_robots_txt_allowed(self):
        """Test robots.txt checking when allowed."""
        scraper = PlaywrightScraper()

        with patch.object(scraper.robots_checker, "is_allowed", return_value=True):
            is_allowed, delay = await scraper._check_robots_txt("https://example.com")

            assert is_allowed is True

    @pytest.mark.asyncio
    async def test_check_robots_txt_blocked(self):
        """Test robots.txt checking when blocked."""
        scraper = PlaywrightScraper()

        with patch.object(scraper.robots_checker, "is_allowed", return_value=False):
            is_allowed, delay = await scraper._check_robots_txt("https://example.com")

            assert is_allowed is False

    @pytest.mark.asyncio
    async def test_is_captcha_page(self):
        """Test CAPTCHA detection."""
        scraper = PlaywrightScraper()

        html_with_captcha = "<html><body><div class='g-recaptcha'></div></body></html>"
        assert scraper._is_captcha_page(html_with_captcha, "https://example.com") is True

        html_without_captcha = "<html><body><h1>Normal Page</h1></body></html>"
        assert scraper._is_captcha_page(html_without_captcha, "https://example.com") is False

    @pytest.mark.asyncio
    async def test_is_rate_limited(self):
        """Test rate limit detection."""
        scraper = PlaywrightScraper()

        # Test with 429 status code
        assert scraper._is_rate_limited(429, "") is True

        # Test with rate limit message
        html = "<html><body>Too many requests</body></html>"
        assert scraper._is_rate_limited(200, html) is True

        # Test normal page
        html = "<html><body>Normal content</body></html>"
        assert scraper._is_rate_limited(200, html) is False


class TestRobotsChecker:
    """Tests for RobotsChecker."""

    @pytest.mark.asyncio
    async def test_robots_checker_initialization(self):
        """Test initializing RobotsChecker."""
        checker = RobotsChecker(
            user_agent="TestBot/1.0",
            cache_ttl_minutes=30,
            timeout=5,
        )

        assert checker.user_agent == "TestBot/1.0"
        assert checker.timeout == 5

    @pytest.mark.asyncio
    async def test_get_robots_url(self):
        """Test getting robots.txt URL."""
        checker = RobotsChecker()

        robots_url = checker._get_robots_url("https://example.com/some/path")
        assert robots_url == "https://example.com/robots.txt"

    @pytest.mark.asyncio
    async def test_get_domain(self):
        """Test extracting domain."""
        checker = RobotsChecker()

        domain = checker._get_domain("https://example.com/path")
        assert domain == "https://example.com"

    @pytest.mark.asyncio
    async def test_is_allowed_no_robots_txt(self):
        """Test is_allowed when no robots.txt exists."""
        checker = RobotsChecker()

        with patch.object(checker, "_fetch_robots_txt", return_value=None):
            is_allowed = await checker.is_allowed("https://example.com/page")
            assert is_allowed is True


class TestContentExtraction:
    """Tests for content extraction utilities."""

    def test_extract_text(self):
        """Test extracting text from HTML."""
        html = """
        <html>
            <head><title>Test</title></head>
            <body>
                <h1>Hello World</h1>
                <p>This is a paragraph.</p>
                <script>console.log('ignored');</script>
            </body>
        </html>
        """

        text = extract_text(html)

        assert "Hello World" in text
        assert "This is a paragraph" in text
        assert "console.log" not in text

    def test_extract_title(self):
        """Test extracting title from HTML."""
        html = """
        <html>
            <head><title>Test Page Title</title></head>
            <body><h1>Content</h1></body>
        </html>
        """

        title = extract_title(html)
        assert title == "Test Page Title"

    def test_extract_title_from_h1(self):
        """Test extracting title from h1 when title tag missing."""
        html = """
        <html>
            <body><h1>Page Heading</h1></body>
        </html>
        """

        title = extract_title(html)
        assert title == "Page Heading"

    def test_extract_links(self):
        """Test extracting links from HTML."""
        html = """
        <html>
            <body>
                <a href="https://example.com/page1">Link 1</a>
                <a href="/relative/path">Link 2</a>
                <a href="#anchor">Link 3</a>
                <a href="mailto:test@example.com">Email</a>
            </body>
        </html>
        """

        links = extract_links(html, "https://example.com")

        assert "https://example.com/page1" in links
        assert "https://example.com/relative/path" in links
        assert any("#" in link for link in links) is False  # Fragments removed
        assert any("mailto:" in link for link in links) is False  # Email links removed

    def test_filter_same_domain(self):
        """Test filtering links by same domain."""
        links = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://other.com/page3",
            "https://subdomain.example.com/page4",
        ]

        filtered = filter_same_domain(links, "https://example.com")

        assert "https://example.com/page1" in filtered
        assert "https://example.com/page2" in filtered
        assert "https://other.com/page3" not in filtered
        assert len(filtered) == 2

    def test_filter_by_tlds(self):
        """Test filtering links by TLDs."""
        links = [
            "https://example.org/page1",
            "https://university.edu/page2",
            "https://company.com/page3",
        ]

        filtered = filter_by_tlds(links, [".org", ".edu"])

        assert "https://example.org/page1" in filtered
        assert "https://university.edu/page2" in filtered
        assert "https://company.com/page3" not in filtered
        assert len(filtered) == 2


class TestScrapingAPI:
    """Tests for scraping API endpoints."""

    @pytest.mark.asyncio
    async def test_create_scraping_job_endpoint(self, client, auth_headers, test_search_session):
        """Test POST /api/scraping/jobs endpoint."""
        response = await client.post(
            "/api/scraping/jobs",
            headers=auth_headers,
            json={
                "session_id": test_search_session.id,
                "name": "Test Scraping Job",
                "depth": 2,
                "domain_filter": "same_domain",
                "delay_min": 1.0,
                "delay_max": 2.0,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Scraping Job"
        assert data["depth"] == 2
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_scraping_job_endpoint(self, client, auth_headers, test_scraping_job):
        """Test GET /api/scraping/jobs/{job_id} endpoint."""
        response = await client.get(
            f"/api/scraping/jobs/{test_scraping_job.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_scraping_job.id
        assert data["name"] == test_scraping_job.name

    @pytest.mark.asyncio
    async def test_list_scraping_jobs_endpoint(self, client, auth_headers, test_user):
        """Test GET /api/scraping/jobs endpoint."""
        response = await client.get(
            "/api/scraping/jobs",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)

    @pytest.mark.asyncio
    async def test_start_scraping_job_endpoint(self, client, auth_headers, test_scraping_job):
        """Test POST /api/scraping/jobs/{job_id}/start endpoint."""
        with patch("backend.services.scraping_service.scrape_session_task") as mock_task:
            mock_task.apply_async.return_value = MagicMock(id="test-task-id")

            response = await client.post(
                f"/api/scraping/jobs/{test_scraping_job.id}/start",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_get_job_statistics_endpoint(self, client, auth_headers, test_scraping_job):
        """Test GET /api/scraping/jobs/{job_id}/statistics endpoint."""
        response = await client.get(
            f"/api/scraping/jobs/{test_scraping_job.id}/statistics",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_urls" in data
        assert "urls_scraped" in data
        assert "progress_percentage" in data


# Pytest fixtures

@pytest.fixture
async def test_search_session(db_session: AsyncSession, test_user):
    """Create a test search session."""
    from backend.models.search import SearchSession

    session = SearchSession(
        user_id=test_user.id,
        name="Test Session",
        status="completed",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest.fixture
async def test_scraping_job(db_session: AsyncSession, test_user, test_search_session):
    """Create a test scraping job."""
    job = ScrapingJob(
        user_id=test_user.id,
        session_id=test_search_session.id,
        name="Test Scraping Job",
        status="pending",
        depth=1,
        domain_filter="same_domain",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job
