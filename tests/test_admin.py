"""Tests for admin endpoints."""
import pytest
from fastapi.testclient import TestClient

from backend.models.user import User


def test_create_user_as_admin(client: TestClient, admin_headers: dict) -> None:
    """Test creating a user as admin."""
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpass123",
            "is_admin": False
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert data["is_admin"] is False


def test_create_user_as_non_admin(client: TestClient, auth_headers: dict) -> None:
    """Test creating a user as non-admin (should fail)."""
    response = client.post(
        "/api/admin/users",
        headers=auth_headers,
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpass123",
            "is_admin": False
        }
    )
    assert response.status_code == 403


def test_create_user_duplicate_username(
    client: TestClient, admin_headers: dict, test_user: User
) -> None:
    """Test creating a user with duplicate username."""
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": "testuser",
            "email": "another@example.com",
            "password": "newpass123",
            "is_admin": False
        }
    )
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]


def test_create_user_duplicate_email(
    client: TestClient, admin_headers: dict, test_user: User
) -> None:
    """Test creating a user with duplicate email."""
    response = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={
            "username": "anotheruser",
            "email": "test@example.com",
            "password": "newpass123",
            "is_admin": False
        }
    )
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


def test_list_users(
    client: TestClient, admin_headers: dict, test_user: User, test_admin: User
) -> None:
    """Test listing all users."""
    response = client.get("/api/admin/users", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2  # At least test_user and test_admin


def test_list_users_as_non_admin(client: TestClient, auth_headers: dict) -> None:
    """Test listing users as non-admin (should fail)."""
    response = client.get("/api/admin/users", headers=auth_headers)
    assert response.status_code == 403


def test_get_user(
    client: TestClient, admin_headers: dict, test_user: User
) -> None:
    """Test getting a specific user."""
    response = client.get(
        f"/api/admin/users/{test_user.id}",
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["username"] == "testuser"


def test_get_nonexistent_user(client: TestClient, admin_headers: dict) -> None:
    """Test getting a nonexistent user."""
    response = client.get("/api/admin/users/99999", headers=admin_headers)
    assert response.status_code == 404


def test_update_user(
    client: TestClient, admin_headers: dict, test_user: User
) -> None:
    """Test updating a user."""
    response = client.patch(
        f"/api/admin/users/{test_user.id}",
        headers=admin_headers,
        json={"email": "updated@example.com"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "updated@example.com"


def test_update_user_duplicate_email(
    client: TestClient, admin_headers: dict, test_user: User, test_admin: User
) -> None:
    """Test updating user with duplicate email."""
    response = client.patch(
        f"/api/admin/users/{test_user.id}",
        headers=admin_headers,
        json={"email": "admin@example.com"}
    )
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


def test_delete_user(
    client: TestClient, admin_headers: dict, test_user: User
) -> None:
    """Test deleting a user."""
    response = client.delete(
        f"/api/admin/users/{test_user.id}",
        headers=admin_headers
    )
    assert response.status_code == 204


def test_delete_self(
    client: TestClient, admin_headers: dict, test_admin: User
) -> None:
    """Test deleting own account (should fail)."""
    response = client.delete(
        f"/api/admin/users/{test_admin.id}",
        headers=admin_headers
    )
    assert response.status_code == 400
    assert "Cannot delete your own account" in response.json()["detail"]


def test_delete_nonexistent_user(client: TestClient, admin_headers: dict) -> None:
    """Test deleting a nonexistent user."""
    response = client.delete("/api/admin/users/99999", headers=admin_headers)
    assert response.status_code == 404
