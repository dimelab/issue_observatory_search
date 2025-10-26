"""Tests for search engines."""
import pytest
from unittest.mock import AsyncMock, patch

from backend.core.search_engines.base import (
    SearchResult,
    SearchEngineConfigError,
    SearchEngineAPIError,
)
from backend.core.search_engines.google_custom import GoogleCustomSearch


def test_google_custom_search_config_validation():
    """Test Google Custom Search configuration validation."""
    # Valid configuration
    engine = GoogleCustomSearch(
        api_key="test_key",
        search_engine_id="test_id"
    )
    assert engine.validate_config() is True

    # Missing API key
    with pytest.raises(SearchEngineConfigError):
        GoogleCustomSearch(api_key="", search_engine_id="test_id")

    # Missing search engine ID
    with pytest.raises(SearchEngineConfigError):
        GoogleCustomSearch(api_key="test_key", search_engine_id="")


def test_google_custom_search_properties():
    """Test Google Custom Search properties."""
    engine = GoogleCustomSearch(
        api_key="test_key",
        search_engine_id="test_id"
    )

    assert engine.name == "google_custom"
    assert engine.max_results_limit == 100


@pytest.mark.asyncio
async def test_google_custom_search_success():
    """Test successful Google Custom Search."""
    engine = GoogleCustomSearch(
        api_key="test_key",
        search_engine_id="test_id"
    )

    # Mock response
    mock_response = {
        "items": [
            {
                "link": "https://example.com/page1",
                "title": "Test Page 1",
                "snippet": "Description 1"
            },
            {
                "link": "https://example.com/page2",
                "title": "Test Page 2",
                "snippet": "Description 2"
            }
        ],
        "searchInformation": {
            "totalResults": "2"
        }
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        results = await engine.search("test query", max_results=10)

        assert len(results) == 2
        assert results[0].url == "https://example.com/page1"
        assert results[0].title == "Test Page 1"
        assert results[0].description == "Description 1"
        assert results[0].rank == 1
        assert results[0].domain == "example.com"


@pytest.mark.asyncio
async def test_google_custom_search_pagination():
    """Test Google Custom Search with pagination."""
    engine = GoogleCustomSearch(
        api_key="test_key",
        search_engine_id="test_id"
    )

    # Mock first page
    mock_response_1 = {
        "items": [
            {
                "link": f"https://example.com/page{i}",
                "title": f"Test Page {i}",
                "snippet": f"Description {i}"
            }
            for i in range(1, 11)  # 10 results
        ],
        "searchInformation": {
            "totalResults": "15"
        }
    }

    # Mock second page
    mock_response_2 = {
        "items": [
            {
                "link": f"https://example.com/page{i}",
                "title": f"Test Page {i}",
                "snippet": f"Description {i}"
            }
            for i in range(11, 16)  # 5 more results
        ],
        "searchInformation": {
            "totalResults": "15"
        }
    }

    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        response = AsyncMock()
        response.status_code = 200
        response.raise_for_status = lambda: None

        if call_count == 1:
            response.json = lambda: mock_response_1
        else:
            response.json = lambda: mock_response_2

        return response

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        results = await engine.search("test query", max_results=15)

        assert len(results) == 15
        assert results[0].rank == 1
        assert results[14].rank == 15


@pytest.mark.asyncio
async def test_google_custom_search_rate_limit_error():
    """Test Google Custom Search rate limit handling."""
    engine = GoogleCustomSearch(
        api_key="test_key",
        search_engine_id="test_id"
    )

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 429
        mock_response.json = lambda: {"error": {"message": "Rate limit exceeded"}}

        from httpx import HTTPStatusError, Response, Request
        error = HTTPStatusError(
            "429 Too Many Requests",
            request=Request("GET", "https://api.example.com"),
            response=mock_response
        )
        mock_get.return_value.raise_for_status.side_effect = error

        from backend.core.search_engines.base import SearchEngineRateLimitError
        with pytest.raises(SearchEngineRateLimitError):
            await engine.search("test query")


@pytest.mark.asyncio
async def test_google_custom_search_api_error():
    """Test Google Custom Search API error handling."""
    engine = GoogleCustomSearch(
        api_key="test_key",
        search_engine_id="test_id"
    )

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.json = lambda: {"error": {"message": "Internal server error"}}

        from httpx import HTTPStatusError, Response, Request
        error = HTTPStatusError(
            "500 Internal Server Error",
            request=Request("GET", "https://api.example.com"),
            response=mock_response
        )
        mock_get.return_value.raise_for_status.side_effect = error

        with pytest.raises(SearchEngineAPIError):
            await engine.search("test query")


@pytest.mark.asyncio
async def test_google_custom_search_no_results():
    """Test Google Custom Search with no results."""
    engine = GoogleCustomSearch(
        api_key="test_key",
        search_engine_id="test_id"
    )

    mock_response = {
        "items": [],
        "searchInformation": {
            "totalResults": "0"
        }
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        results = await engine.search("nonexistent query")

        assert len(results) == 0


def test_google_custom_search_domain_extraction():
    """Test domain extraction from URLs."""
    engine = GoogleCustomSearch(
        api_key="test_key",
        search_engine_id="test_id"
    )

    # Test various URL formats
    assert engine._extract_domain("https://www.example.com/page") == "www.example.com"
    assert engine._extract_domain("http://example.com") == "example.com"
    assert engine._extract_domain("https://subdomain.example.com/path/to/page") == "subdomain.example.com"
    assert engine._extract_domain("invalid-url") == ""
