"""Tests for Serper search engine."""
import pytest
from unittest.mock import AsyncMock, patch

from backend.core.search_engines.base import (
    SearchEngineConfigError,
    SearchEngineAPIError,
    SearchEngineRateLimitError,
)
from backend.core.search_engines.serper import SerperSearch


def test_serper_search_config_validation():
    """Test Serper search engine configuration validation."""
    # Valid configuration
    engine = SerperSearch(api_key="test_key")
    assert engine.validate_config() is True

    # Missing API key
    with pytest.raises(SearchEngineConfigError):
        SerperSearch(api_key="")

    # No API key provided
    with pytest.raises(SearchEngineConfigError):
        SerperSearch(api_key=None)


def test_serper_search_properties():
    """Test Serper search engine properties."""
    engine = SerperSearch(api_key="test_key")

    assert engine.name == "serper"
    assert engine.max_results_limit == 100


@pytest.mark.asyncio
async def test_serper_search_success():
    """Test successful Serper search."""
    engine = SerperSearch(api_key="test_key")

    # Mock response
    mock_response = {
        "organic": [
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
        "searchParameters": {
            "q": "test query",
            "type": "search"
        }
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )

        results = await engine.search("test query", max_results=10)

        assert len(results) == 2
        assert results[0].url == "https://example.com/page1"
        assert results[0].title == "Test Page 1"
        assert results[0].description == "Description 1"
        assert results[0].rank == 1
        assert results[0].domain == "example.com"

        assert results[1].url == "https://example.com/page2"
        assert results[1].title == "Test Page 2"
        assert results[1].rank == 2


@pytest.mark.asyncio
async def test_serper_search_with_location():
    """Test Serper search with location parameter."""
    engine = SerperSearch(api_key="test_key")

    mock_response = {
        "organic": [
            {
                "link": "https://example.dk/page1",
                "title": "Danish Page",
                "snippet": "Description"
            }
        ],
        "searchParameters": {
            "q": "test",
            "location": "Denmark"
        }
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )

        results = await engine.search(
            "test",
            max_results=10,
            location="Denmark",
            gl="dk",
            hl="da"
        )

        assert len(results) == 1
        assert results[0].domain == "example.dk"

        # Verify request payload
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["location"] == "Denmark"
        assert payload["gl"] == "dk"
        assert payload["hl"] == "da"


@pytest.mark.asyncio
async def test_serper_search_max_results():
    """Test Serper search with max results."""
    engine = SerperSearch(api_key="test_key")

    # Create 50 mock results
    mock_results = [
        {
            "link": f"https://example.com/page{i}",
            "title": f"Test Page {i}",
            "snippet": f"Description {i}"
        }
        for i in range(1, 51)
    ]

    mock_response = {
        "organic": mock_results,
        "searchParameters": {"q": "test"}
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )

        # Request 50 results
        results = await engine.search("test query", max_results=50)

        assert len(results) == 50
        assert results[0].rank == 1
        assert results[49].rank == 50

        # Verify request asked for 50 results
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["num"] == 50


@pytest.mark.asyncio
async def test_serper_search_rate_limit_error():
    """Test Serper search rate limit handling."""
    engine = SerperSearch(api_key="test_key")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=429,
            text="Rate limit exceeded"
        )

        with pytest.raises(SearchEngineRateLimitError):
            await engine.search("test query")


@pytest.mark.asyncio
async def test_serper_search_auth_error():
    """Test Serper search authentication error."""
    engine = SerperSearch(api_key="invalid_key")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=401,
            text="Unauthorized"
        )

        with pytest.raises(SearchEngineAPIError, match="Invalid Serper API key"):
            await engine.search("test query")


@pytest.mark.asyncio
async def test_serper_search_api_error():
    """Test Serper search API error handling."""
    engine = SerperSearch(api_key="test_key")

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=500,
            text="Internal server error"
        )

        with pytest.raises(SearchEngineAPIError):
            await engine.search("test query")


@pytest.mark.asyncio
async def test_serper_search_timeout_error():
    """Test Serper search timeout handling."""
    engine = SerperSearch(api_key="test_key", timeout=5)

    with patch("httpx.AsyncClient.post") as mock_post:
        from httpx import TimeoutException
        mock_post.side_effect = TimeoutException("Request timeout")

        with pytest.raises(SearchEngineAPIError, match="timed out"):
            await engine.search("test query")


@pytest.mark.asyncio
async def test_serper_search_no_results():
    """Test Serper search with no results."""
    engine = SerperSearch(api_key="test_key")

    mock_response = {
        "organic": [],
        "searchParameters": {"q": "nonexistent query"}
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )

        results = await engine.search("nonexistent query")

        assert len(results) == 0


@pytest.mark.asyncio
async def test_serper_search_malformed_results():
    """Test Serper search with malformed results."""
    engine = SerperSearch(api_key="test_key")

    # Results missing required fields
    mock_response = {
        "organic": [
            {
                "link": "https://example.com/page1",
                "title": "Test Page 1",
                "snippet": "Description 1"
            },
            {
                # Missing link
                "title": "Test Page 2",
                "snippet": "Description 2"
            },
            {
                "link": "https://example.com/page3",
                # Missing title
                "snippet": "Description 3"
            }
        ]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )

        results = await engine.search("test query")

        # Should only include the valid result
        assert len(results) == 1
        assert results[0].url == "https://example.com/page1"


def test_serper_domain_extraction():
    """Test domain extraction from URLs."""
    engine = SerperSearch(api_key="test_key")

    # Test various URL formats
    assert engine._extract_domain("https://www.example.com/page") == "www.example.com"
    assert engine._extract_domain("http://example.com") == "example.com"
    assert engine._extract_domain("https://subdomain.example.com/path/to/page") == "subdomain.example.com"
    assert engine._extract_domain("invalid-url") == ""


@pytest.mark.asyncio
async def test_serper_search_max_results_limit():
    """Test that Serper respects max results limit."""
    engine = SerperSearch(api_key="test_key")

    # Create 150 mock results (more than the limit)
    mock_results = [
        {
            "link": f"https://example.com/page{i}",
            "title": f"Test Page {i}",
            "snippet": f"Description {i}"
        }
        for i in range(1, 151)
    ]

    mock_response = {
        "organic": mock_results,
        "searchParameters": {"q": "test"}
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )

        # Request 150 results (more than the limit of 100)
        results = await engine.search("test query", max_results=150)

        # Should cap at 100
        assert len(results) == 100

        # Verify request asked for 100 (the capped value)
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["num"] == 100


@pytest.mark.asyncio
async def test_serper_get_search_metadata():
    """Test getting search metadata."""
    engine = SerperSearch(api_key="test_key")

    mock_response = {
        "organic": [],
        "searchParameters": {
            "q": "test query",
            "type": "search",
            "engine": "google"
        },
        "knowledgeGraph": {
            "title": "Test Topic",
            "description": "Description of test topic"
        },
        "relatedSearches": [
            {"query": "related search 1"},
            {"query": "related search 2"}
        ],
        "peopleAlsoAsk": [
            {"question": "What is test?", "snippet": "Answer 1"},
            {"question": "How does test work?", "snippet": "Answer 2"}
        ]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response,
            raise_for_status=lambda: None
        )

        metadata = await engine.get_search_metadata("test query")

        assert "search_parameters" in metadata
        assert metadata["search_parameters"]["q"] == "test query"
        assert "knowledge_graph" in metadata
        assert metadata["knowledge_graph"]["title"] == "Test Topic"
        assert "related_searches" in metadata
        assert len(metadata["related_searches"]) == 2
        assert "people_also_ask" in metadata
        assert len(metadata["people_also_ask"]) == 2


@pytest.mark.asyncio
async def test_serper_headers():
    """Test that Serper sets correct headers."""
    engine = SerperSearch(api_key="test_api_key_12345")

    mock_response = {
        "organic": [],
        "searchParameters": {"q": "test"}
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )

        await engine.search("test query")

        # Verify headers
        call_args = mock_post.call_args
        headers = call_args.kwargs["headers"]
        assert headers["X-API-KEY"] == "test_api_key_12345"
        assert headers["Content-Type"] == "application/json"
