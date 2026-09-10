"""Redis caching implementation with TTL, invalidation, and namespacing."""
import json
import logging
from typing import Any, Optional, Callable, TypeVar, Union
from redis.asyncio import Redis, ConnectionPool
from backend.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RedisCache:
    """
    Centralized Redis caching with TTL, invalidation, and namespacing.

    Provides high-performance caching for:
    - Search results (1 hour TTL)
    - Network metadata (24 hours TTL)
    - Analysis results (1 hour TTL)
    - User preferences (12 hours TTL)
    - Session lists (5 minutes TTL)
    - Statistics (15 minutes TTL)

    Features:
    - Automatic JSON serialization/deserialization
    - Namespace support for key organization
    - Pattern-based bulk deletion
    - TTL management
    - Connection pooling

    Example:
        cache = RedisCache(redis_client, namespace="search")

        # Set value with 1 hour TTL
        await cache.set("results:123", data, ttl=3600)

        # Get value
        data = await cache.get("results:123")

        # Delete pattern
        await cache.delete_pattern("results:*")
    """

    def __init__(self, redis_client: Redis, namespace: str = "io"):
        """
        Initialize Redis cache.

        Args:
            redis_client: Redis client instance
            namespace: Cache key namespace prefix (default: "io")
        """
        self.redis = redis_client
        self.namespace = namespace

    def _make_key(self, key: str) -> str:
        """
        Create namespaced cache key.

        Args:
            key: Original key

        Returns:
            Namespaced key (e.g., "io:search:results:123")
        """
        return f"{self.namespace}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """
        Get cached value.

        Args:
            key: Cache key

        Returns:
            Cached value (deserialized from JSON) or None if not found
        """
        try:
            namespaced_key = self._make_key(key)
            value = await self.redis.get(namespaced_key)

            if value is None:
                logger.debug(f"Cache miss: {namespaced_key}")
                return None

            logger.debug(f"Cache hit: {namespaced_key}")
            return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600
    ) -> bool:
        """
        Set cached value with TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds (default: 3600 = 1 hour)

        Returns:
            True if successful, False otherwise
        """
        try:
            namespaced_key = self._make_key(key)
            serialized = json.dumps(value, default=str)

            await self.redis.setex(
                namespaced_key,
                ttl,
                serialized
            )

            logger.debug(f"Cache set: {namespaced_key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete cached value.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False otherwise
        """
        try:
            namespaced_key = self._make_key(key)
            deleted = await self.redis.delete(namespaced_key)

            logger.debug(f"Cache delete: {namespaced_key} (deleted: {deleted})")
            return deleted > 0
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete keys matching pattern.

        Args:
            pattern: Key pattern (e.g., "search:*" for all search keys)

        Returns:
            Number of keys deleted
        """
        try:
            namespaced_pattern = self._make_key(pattern)

            # Scan for matching keys
            deleted_count = 0
            async for key in self.redis.scan_iter(match=namespaced_pattern, count=100):
                await self.redis.delete(key)
                deleted_count += 1

            logger.info(f"Cache pattern delete: {namespaced_pattern} ({deleted_count} keys)")
            return deleted_count
        except Exception as e:
            logger.error(f"Cache pattern delete error for pattern {pattern}: {e}")
            return 0

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl: int = 3600
    ) -> Optional[T]:
        """
        Get from cache or compute and cache.

        Args:
            key: Cache key
            factory: Callable that computes the value if not in cache
            ttl: Time-to-live in seconds (default: 3600 = 1 hour)

        Returns:
            Cached or computed value

        Example:
            async def expensive_query():
                return await db.execute(complex_query)

            result = await cache.get_or_set(
                "query:results:123",
                expensive_query,
                ttl=3600
            )
        """
        # Try to get from cache
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value

        # Cache miss - compute value
        try:
            value = await factory() if callable(factory) else factory

            # Cache the result
            await self.set(key, value, ttl=ttl)

            return value
        except Exception as e:
            logger.error(f"Factory function error for key {key}: {e}")
            return None

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        try:
            namespaced_key = self._make_key(key)
            return await self.redis.exists(namespaced_key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for key.

        Args:
            key: Cache key

        Returns:
            Remaining TTL in seconds, or None if key doesn't exist
        """
        try:
            namespaced_key = self._make_key(key)
            ttl = await self.redis.ttl(namespaced_key)

            if ttl < 0:
                return None

            return ttl
        except Exception as e:
            logger.error(f"Cache TTL error for key {key}: {e}")
            return None

    async def increment(
        self,
        key: str,
        amount: int = 1,
        ttl: Optional[int] = None
    ) -> Optional[int]:
        """
        Increment counter in cache.

        Args:
            key: Cache key
            amount: Amount to increment (default: 1)
            ttl: Set TTL if key is created (optional)

        Returns:
            New value after increment, or None on error
        """
        try:
            namespaced_key = self._make_key(key)
            new_value = await self.redis.incrby(namespaced_key, amount)

            # Set TTL if provided and key was just created
            if ttl is not None and new_value == amount:
                await self.redis.expire(namespaced_key, ttl)

            return new_value
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return None

    async def flush_namespace(self) -> int:
        """
        Delete all keys in this namespace.

        Returns:
            Number of keys deleted
        """
        return await self.delete_pattern("*")


# Global Redis client and cache instances
_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None
_cache_instances: dict[str, RedisCache] = {}


async def get_redis_client() -> Redis:
    """
    Get or create global Redis client with connection pooling.

    Returns:
        Redis client instance
    """
    global _redis_pool, _redis_client

    if _redis_client is None:
        # Create connection pool
        _redis_pool = ConnectionPool.from_url(
            str(settings.redis_url),
            max_connections=settings.redis_max_connections,
            decode_responses=True,
        )

        # Create Redis client
        _redis_client = Redis(connection_pool=_redis_pool)

        logger.info(
            f"Redis client initialized with pool size {settings.redis_max_connections}"
        )

    return _redis_client


async def get_redis_cache(namespace: str = "io") -> RedisCache:
    """
    Get or create Redis cache instance for namespace.

    Args:
        namespace: Cache namespace (default: "io")

    Returns:
        RedisCache instance
    """
    global _cache_instances

    if namespace not in _cache_instances:
        redis_client = await get_redis_client()
        _cache_instances[namespace] = RedisCache(redis_client, namespace)
        logger.info(f"Redis cache created for namespace: {namespace}")

    return _cache_instances[namespace]


async def close_redis():
    """Close Redis connections."""
    global _redis_client, _redis_pool, _cache_instances

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None

    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None

    _cache_instances.clear()

    logger.info("Redis connections closed")
