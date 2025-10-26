"""Caching for analysis results using Redis."""
import asyncio
import json
import logging
from typing import Optional, Any, Dict
import redis.asyncio as redis

from backend.config import settings

logger = logging.getLogger(__name__)


class AnalysisCache:
    """
    Cache for analysis results to improve performance.

    Uses Redis for distributed caching with TTL-based expiration.
    Caches both full analysis results and individual components (nouns, entities).

    Example:
        >>> cache = AnalysisCache()
        >>> await cache.cache_analysis(123, {"nouns": [...], "entities": [...]})
        >>> result = await cache.get_cached_analysis(123)
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize the analysis cache.

        Args:
            redis_client: Optional Redis client. If None, creates a new one.
        """
        self._redis_client = redis_client
        self._redis_url = str(settings.redis_url)
        self._cache_ttl = settings.nlp_cache_ttl

    async def _get_redis(self) -> redis.Redis:
        """
        Get or create Redis connection.

        Returns:
            Redis client instance
        """
        if self._redis_client is None:
            self._redis_client = await redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis_client

    def _make_key(self, prefix: str, content_id: int) -> str:
        """
        Create a cache key for a content ID.

        Args:
            prefix: Key prefix (e.g., "analysis", "nouns", "entities")
            content_id: Website content ID

        Returns:
            Cache key string
        """
        return f"analysis:{prefix}:{content_id}"

    async def get_cached_analysis(self, content_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached full analysis results.

        Args:
            content_id: Website content ID

        Returns:
            Dictionary with analysis results or None if not cached
        """
        try:
            redis_client = await self._get_redis()
            key = self._make_key("full", content_id)

            cached_data = await redis_client.get(key)
            if cached_data:
                logger.debug(f"Cache hit for analysis: content_id={content_id}")
                return json.loads(cached_data)

            logger.debug(f"Cache miss for analysis: content_id={content_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting cached analysis: {e}")
            return None

    async def cache_analysis(
        self, content_id: int, results: Dict[str, Any]
    ) -> bool:
        """
        Cache full analysis results.

        Args:
            content_id: Website content ID
            results: Analysis results dictionary

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis()
            key = self._make_key("full", content_id)

            await redis_client.setex(
                key, self._cache_ttl, json.dumps(results, default=str)
            )

            logger.debug(
                f"Cached analysis for content_id={content_id} "
                f"(TTL={self._cache_ttl}s)"
            )
            return True

        except Exception as e:
            logger.error(f"Error caching analysis: {e}")
            return False

    async def get_cached_nouns(self, content_id: int) -> Optional[list]:
        """
        Get cached nouns for a content.

        Args:
            content_id: Website content ID

        Returns:
            List of noun dictionaries or None if not cached
        """
        try:
            redis_client = await self._get_redis()
            key = self._make_key("nouns", content_id)

            cached_data = await redis_client.get(key)
            if cached_data:
                logger.debug(f"Cache hit for nouns: content_id={content_id}")
                return json.loads(cached_data)

            return None

        except Exception as e:
            logger.error(f"Error getting cached nouns: {e}")
            return None

    async def cache_nouns(self, content_id: int, nouns: list) -> bool:
        """
        Cache nouns for a content.

        Args:
            content_id: Website content ID
            nouns: List of noun dictionaries

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis()
            key = self._make_key("nouns", content_id)

            await redis_client.setex(
                key, self._cache_ttl, json.dumps(nouns, default=str)
            )

            logger.debug(
                f"Cached {len(nouns)} nouns for content_id={content_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error caching nouns: {e}")
            return False

    async def get_cached_entities(self, content_id: int) -> Optional[list]:
        """
        Get cached entities for a content.

        Args:
            content_id: Website content ID

        Returns:
            List of entity dictionaries or None if not cached
        """
        try:
            redis_client = await self._get_redis()
            key = self._make_key("entities", content_id)

            cached_data = await redis_client.get(key)
            if cached_data:
                logger.debug(f"Cache hit for entities: content_id={content_id}")
                return json.loads(cached_data)

            return None

        except Exception as e:
            logger.error(f"Error getting cached entities: {e}")
            return None

    async def cache_entities(self, content_id: int, entities: list) -> bool:
        """
        Cache entities for a content.

        Args:
            content_id: Website content ID
            entities: List of entity dictionaries

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis()
            key = self._make_key("entities", content_id)

            await redis_client.setex(
                key, self._cache_ttl, json.dumps(entities, default=str)
            )

            logger.debug(
                f"Cached {len(entities)} entities for content_id={content_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error caching entities: {e}")
            return False

    async def invalidate_analysis(self, content_id: int) -> bool:
        """
        Invalidate all cached data for a content.

        Args:
            content_id: Website content ID

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            redis_client = await self._get_redis()

            keys_to_delete = [
                self._make_key("full", content_id),
                self._make_key("nouns", content_id),
                self._make_key("entities", content_id),
            ]

            deleted_count = await redis_client.delete(*keys_to_delete)

            logger.debug(
                f"Invalidated {deleted_count} cache entries for "
                f"content_id={content_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return False

    async def invalidate_batch(self, content_ids: list[int]) -> int:
        """
        Invalidate cached data for multiple contents.

        Args:
            content_ids: List of website content IDs

        Returns:
            Number of cache entries deleted
        """
        if not content_ids:
            return 0

        try:
            redis_client = await self._get_redis()

            # Build list of all keys to delete
            keys_to_delete = []
            for content_id in content_ids:
                keys_to_delete.extend(
                    [
                        self._make_key("full", content_id),
                        self._make_key("nouns", content_id),
                        self._make_key("entities", content_id),
                    ]
                )

            deleted_count = await redis_client.delete(*keys_to_delete)

            logger.info(
                f"Invalidated {deleted_count} cache entries for "
                f"{len(content_ids)} contents"
            )
            return deleted_count

        except Exception as e:
            logger.error(f"Error invalidating batch cache: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        try:
            redis_client = await self._get_redis()

            # Get info from Redis
            info = await redis_client.info("stats")

            # Count analysis keys
            pattern = "analysis:*"
            cursor = 0
            key_count = 0

            while True:
                cursor, keys = await redis_client.scan(
                    cursor, match=pattern, count=100
                )
                key_count += len(keys)
                if cursor == 0:
                    break

            return {
                "total_keys": key_count,
                "ttl_seconds": self._cache_ttl,
                "redis_connected": True,
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "total_keys": 0,
                "ttl_seconds": self._cache_ttl,
                "redis_connected": False,
                "error": str(e),
            }

    async def clear_all_analysis_cache(self) -> int:
        """
        Clear all analysis cache entries.

        WARNING: This deletes all analysis cache data.

        Returns:
            Number of keys deleted
        """
        try:
            redis_client = await self._get_redis()

            # Find all analysis keys
            pattern = "analysis:*"
            keys_to_delete = []
            cursor = 0

            while True:
                cursor, keys = await redis_client.scan(
                    cursor, match=pattern, count=1000
                )
                keys_to_delete.extend(keys)
                if cursor == 0:
                    break

            if keys_to_delete:
                deleted_count = await redis_client.delete(*keys_to_delete)
                logger.warning(
                    f"Cleared all analysis cache: deleted {deleted_count} keys"
                )
                return deleted_count

            return 0

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

    async def close(self):
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
            logger.debug("Closed Redis connection")


# Global cache instance
_cache_instance: Optional[AnalysisCache] = None


async def get_analysis_cache() -> AnalysisCache:
    """
    Get global analysis cache instance.

    Returns:
        AnalysisCache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = AnalysisCache()
    return _cache_instance
