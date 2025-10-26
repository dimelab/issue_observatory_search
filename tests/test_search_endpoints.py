"""Tests for search API endpoints."""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.models.user import User
from backend.models.search import SearchSession, SearchQuery, SearchResult


@pytest.fixture
async def search_session(db_session, test_user):
    """Create a test search session."""
    session = SearchSession(
        user_id=test_user.id,
        name="Test Search",
        status="completed"
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest.fixture
async def search_query(db_session, search_session):
    """Create a test search query with results."""
    query = SearchQuery(
        session_id=search_session.id,
        query_text="test query",
        search_engine="google_custom",
        max_results=10,
        status="completed",
        result_count=2
    )
    db_session.add(query)
    await db_session.commit()
    await db_session.refresh(query)

    # Add some results
    for i in range(1, 3):
        result = SearchResult(
            query_id=query.id,
            url=f"https://example.com/page{i}",
            title=f"Test Page {i}",
            description=f"Description {i}",
            rank=i,
            domain="example.com",
            scraped=False
        )
        db_session.add(result)

    await db_session.commit()
    return query


def test_execute_search_success(client, auth_headers):
    """Test successful search execution."""
    mock_results = [
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
    ]

    mock_response = {
        "items": mock_results,
        "searchInformation": {"totalResults": "2"}
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        response = client.post(
            "/api/search/execute",
            headers=auth_headers,
            json={
                "session_name": "Test Search Session",
                "queries": ["test query"],
                "search_engine": "google_custom",
                "max_results": 10
            }
        )

        assert response.status_code == 202
        data = response.json()
        assert "session_id" in data
        assert data["status"] in ["processing", "completed"]
        assert "status_url" in data


def test_execute_search_unauthorized(client):
    """Test search execution without authentication."""
    response = client.post(
        "/api/search/execute",
        json={
            "session_name": "Test Search",
            "queries": ["test"],
            "search_engine": "google_custom",
            "max_results": 10
        }
    )
    assert response.status_code == 403


def test_execute_search_invalid_engine(client, auth_headers):
    """Test search with invalid search engine."""
    response = client.post(
        "/api/search/execute",
        headers=auth_headers,
        json={
            "session_name": "Test Search",
            "queries": ["test"],
            "search_engine": "invalid_engine",
            "max_results": 10
        }
    )
    assert response.status_code == 422  # Validation error


def test_execute_search_invalid_domains(client, auth_headers):
    """Test search with invalid domain format."""
    response = client.post(
        "/api/search/execute",
        headers=auth_headers,
        json={
            "session_name": "Test Search",
            "queries": ["test"],
            "search_engine": "google_custom",
            "max_results": 10,
            "allowed_domains": ["dk", "com"]  # Missing dots
        }
    )
    assert response.status_code == 422  # Validation error


def test_execute_search_with_domain_filter(client, auth_headers):
    """Test search with domain filter."""
    mock_results = [
        {
            "link": "https://example.dk/page1",
            "title": "Danish Page",
            "snippet": "Description"
        }
    ]

    mock_response = {
        "items": mock_results,
        "searchInformation": {"totalResults": "1"}
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        response = client.post(
            "/api/search/execute",
            headers=auth_headers,
            json={
                "session_name": "Danish Search",
                "queries": ["test"],
                "search_engine": "google_custom",
                "max_results": 10,
                "allowed_domains": [".dk"]
            }
        )

        assert response.status_code == 202


def test_list_sessions(client, auth_headers, search_session):
    """Test listing search sessions."""
    response = client.get(
        "/api/search/sessions",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert len(data["sessions"]) >= 1


def test_list_sessions_pagination(client, auth_headers, search_session):
    """Test search sessions pagination."""
    response = client.get(
        "/api/search/sessions?page=1&per_page=5",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["per_page"] == 5


def test_list_sessions_unauthorized(client):
    """Test listing sessions without authentication."""
    response = client.get("/api/search/sessions")
    assert response.status_code == 403


def test_get_session(client, auth_headers, search_session, search_query):
    """Test getting a specific search session."""
    response = client.get(
        f"/api/search/session/{search_session.id}",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == search_session.id
    assert data["name"] == "Test Search"
    assert "queries" in data
    assert len(data["queries"]) >= 1

    # Check query details
    query_data = data["queries"][0]
    assert query_data["query_text"] == "test query"
    assert "results" in query_data
    assert len(query_data["results"]) == 2


def test_get_session_not_found(client, auth_headers):
    """Test getting non-existent session."""
    response = client.get(
        "/api/search/session/99999",
        headers=auth_headers
    )
    assert response.status_code == 404


def test_get_session_unauthorized(client, search_session):
    """Test getting session without authentication."""
    response = client.get(f"/api/search/session/{search_session.id}")
    assert response.status_code == 403


def test_delete_session(client, auth_headers, search_session):
    """Test deleting a search session."""
    response = client.delete(
        f"/api/search/session/{search_session.id}",
        headers=auth_headers
    )

    assert response.status_code == 204

    # Verify deletion
    response = client.get(
        f"/api/search/session/{search_session.id}",
        headers=auth_headers
    )
    assert response.status_code == 404


def test_delete_session_not_found(client, auth_headers):
    """Test deleting non-existent session."""
    response = client.delete(
        "/api/search/session/99999",
        headers=auth_headers
    )
    assert response.status_code == 404


def test_delete_session_unauthorized(client, search_session):
    """Test deleting session without authentication."""
    response = client.delete(f"/api/search/session/{search_session.id}")
    assert response.status_code == 403


def test_search_deduplication(client, auth_headers):
    """Test that duplicate URLs are removed across queries."""
    # Mock same URL returned for different queries
    mock_results = [
        {
            "link": "https://example.com/same-page",
            "title": "Same Page",
            "snippet": "Description"
        }
    ]

    mock_response = {
        "items": mock_results,
        "searchInformation": {"totalResults": "1"}
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        mock_get.return_value.raise_for_status = lambda: None

        response = client.post(
            "/api/search/execute",
            headers=auth_headers,
            json={
                "session_name": "Dedup Test",
                "queries": ["query1", "query2"],  # Both will return same URL
                "search_engine": "google_custom",
                "max_results": 10
            }
        )

        assert response.status_code == 202
        session_id = response.json()["session_id"]

        # Get session details
        response = client.get(
            f"/api/search/session/{session_id}",
            headers=auth_headers
        )

        data = response.json()
        # Should have 2 queries
        assert len(data["queries"]) == 2

        # But only 1 unique result total (deduplication worked)
        total_results = sum(len(q["results"]) for q in data["queries"])
        assert total_results == 1
