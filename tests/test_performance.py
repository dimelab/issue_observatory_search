"""
Tests for performance features: caching, bulk operations, pagination.

Tests cover:
- Redis caching functionality
- Bulk insert/update operations
- Pagination
- Query optimization
"""
import pytest
from unittest.mock import AsyncMock, patch
from backend.core.cache.redis_cache import (
    get_cache,
    set_cache,
    delete_cache,
    clear_cache_pattern,
)


@pytest.mark.asyncio
class TestCaching:
    """Tests for Redis caching."""

    async def test_set_and_get_cache(self):
        """Test setting and getting cache values."""
        key = "test_key"
        value = {"data": "test_value"}

        # Set cache
        await set_cache(key, value, ttl=60)

        # Get cache
        result = await get_cache(key)
        assert result == value

    async def test_cache_expiry(self):
        """Test cache expiration."""
        key = "expiry_test"
        value = "test"

        # Set cache with 1 second TTL
        await set_cache(key, value, ttl=1)

        # Should exist immediately
        result = await get_cache(key)
        assert result == value

        # After expiry, should return None
        import asyncio
        await asyncio.sleep(2)
        result = await get_cache(key)
        assert result is None

    async def test_delete_cache(self):
        """Test cache deletion."""
        key = "delete_test"
        value = "test"

        await set_cache(key, value)
        assert await get_cache(key) == value

        await delete_cache(key)
        assert await get_cache(key) is None

    async def test_cache_pattern_clear(self):
        """Test clearing cache by pattern."""
        # Set multiple keys with pattern
        await set_cache("user:1:profile", {"name": "User 1"})
        await set_cache("user:2:profile", {"name": "User 2"})
        await set_cache("other:data", {"data": "keep this"})

        # Clear user pattern
        await clear_cache_pattern("user:*")

        # User keys should be gone
        assert await get_cache("user:1:profile") is None
        assert await get_cache("user:2:profile") is None

        # Other data should remain
        assert await get_cache("other:data") is not None


class TestPagination:
    """Tests for pagination functionality."""

    def test_pagination_validation(self):
        """Test pagination parameter validation."""
        from backend.security.validator import InputValidator

        # Valid pagination
        page, per_page = InputValidator.validate_pagination(1, 50)
        assert page == 1
        assert per_page == 50

        # Invalid page (< 1)
        with pytest.raises(Exception):
            InputValidator.validate_pagination(0, 50)

        # Invalid per_page (> max)
        with pytest.raises(Exception):
            InputValidator.validate_pagination(1, 1000, max_per_page=500)
