"""Tests for authentication endpoints."""
import pytest
from fastapi.testclient import TestClient

from backend.models.user import User


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_login_success(client: TestClient, test_user: User) -> None:
    """Test successful login."""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "testuser"
    assert data["user"]["email"] == "test@example.com"


def test_login_invalid_username(client: TestClient) -> None:
    """Test login with invalid username."""
    response = client.post(
        "/api/auth/login",
        json={"username": "nonexistent", "password": "password"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_invalid_password(client: TestClient, test_user: User) -> None:
    """Test login with invalid password."""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_get_current_user(client: TestClient, auth_headers: dict) -> None:
    """Test getting current user information."""
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["is_admin"] is False


def test_get_current_user_unauthorized(client: TestClient) -> None:
    """Test getting current user without authentication."""
    response = client.get("/api/auth/me")
    assert response.status_code == 403


def test_get_current_user_invalid_token(client: TestClient) -> None:
    """Test getting current user with invalid token."""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401


def test_logout(client: TestClient, auth_headers: dict) -> None:
    """Test logout endpoint."""
    response = client.post("/api/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]
