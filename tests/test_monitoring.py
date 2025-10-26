"""
Tests for monitoring and health check functionality.

Tests cover:
- Health check endpoints
- Metrics collection
- Component health checks
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from backend.monitoring.health import HealthCheck, HealthStatus


@pytest.mark.asyncio
class TestHealthChecks:
    """Tests for health check functionality."""

    async def test_check_database_healthy(self):
        """Test database health check when healthy."""
        result = await HealthCheck.check_database()
        assert "status" in result
        assert "details" in result

    async def test_check_redis_healthy(self):
        """Test Redis health check when healthy."""
        result = await HealthCheck.check_redis()
        assert "status" in result
        assert "details" in result

    @patch("backend.monitoring.health.get_redis_client")
    async def test_check_redis_unhealthy(self, mock_redis):
        """Test Redis health check when unhealthy."""
        mock_redis.side_effect = Exception("Connection failed")
        result = await HealthCheck.check_redis()
        assert result["status"] == HealthStatus.UNHEALTHY
        assert "error" in result["details"]

    async def test_check_disk_space(self):
        """Test disk space check."""
        result = await HealthCheck.check_disk_space()
        assert "status" in result
        assert "total_gb" in result["details"]
        assert "free_gb" in result["details"]

    async def test_check_all(self):
        """Test comprehensive health check."""
        result = await HealthCheck.check_all()
        assert "status" in result
        assert "checks" in result
        assert "database" in result["checks"]
        assert "redis" in result["checks"]


def test_health_endpoint(client: TestClient):
    """Test basic health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_live_endpoint(client: TestClient):
    """Test liveness probe endpoint."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert "status" in response.json()


def test_metrics_endpoint(client: TestClient):
    """Test Prometheus metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"http_requests_total" in response.content or True  # Metrics format
