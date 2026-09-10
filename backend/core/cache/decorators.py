"""Caching decorators for function result caching and invalidation."""
import functools
import inspect
import logging
from typing import Callable, Any, Optional
from backend.core.cache.redis_cache import get_redis_cache

logger = logging.getLogger(__name__)


def cached(
    key_pattern: str,
    ttl: int = 3600,
    namespace: str = "io"
):
    """
    Decorator for caching function results.

    Caches the return value of async functions using Redis.
    Supports dynamic key generation using function parameters.

    Args:
        key_pattern: Cache key pattern with {param} placeholders
        ttl: Time-to-live in seconds (default: 3600 = 1 hour)
        namespace: Cache namespace (default: "io")

    Example:
        @cached("search:results:{session_id}", ttl=3600)
        async def get_search_results(session_id: int):
            # Expensive database query
            return results

        # First call - executes function and caches result
        results = await get_search_results(123)

        # Second call - returns cached result
        results = await get_search_results(123)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Get cache instance
            cache = await get_redis_cache(namespace)

            # Get function signature to map args to kwargs
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            all_kwargs = bound_args.arguments

            # Generate cache key from pattern
            try:
                cache_key = key_pattern.format(**all_kwargs)
            except KeyError as e:
                logger.warning(
                    f"Cache key pattern '{key_pattern}' missing parameter: {e}. "
                    "Skipping cache."
                )
                return await func(*args, **kwargs)

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                return cached_value

            # Cache miss - execute function
            logger.debug(f"Cache miss for {func.__name__}: {cache_key}")
            result = await func(*args, **kwargs)

            # Cache the result
            await cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper
    return decorator


def cache_invalidate(
    pattern: str,
    namespace: str = "io"
):
    """
    Decorator for cache invalidation.

    Invalidates cache keys matching pattern after function execution.
    Supports dynamic pattern generation using function parameters.

    Args:
        pattern: Cache key pattern with {param} placeholders
        namespace: Cache namespace (default: "io")

    Example:
        @cache_invalidate("search:*:{session_id}")
        async def update_search_session(session_id: int, data: dict):
            # Update database
            ...

        # After this call, all cache keys matching "search:*:123" are deleted
        await update_search_session(123, {"name": "Updated"})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Execute function first
            result = await func(*args, **kwargs)

            # Get cache instance
            cache = await get_redis_cache(namespace)

            # Get function signature to map args to kwargs
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            all_kwargs = bound_args.arguments

            # Generate invalidation pattern from template
            try:
                invalidation_pattern = pattern.format(**all_kwargs)
            except KeyError as e:
                logger.warning(
                    f"Cache invalidation pattern '{pattern}' missing parameter: {e}. "
                    "Skipping invalidation."
                )
                return result

            # Invalidate matching keys
            deleted_count = await cache.delete_pattern(invalidation_pattern)
            logger.info(
                f"Cache invalidation for {func.__name__}: "
                f"pattern='{invalidation_pattern}', deleted={deleted_count}"
            )

            return result

        return wrapper
    return decorator


def cache_key(*key_params: str):
    """
    Decorator to specify which function parameters to use as cache key.

    Simpler alternative to cached() when you want to cache by specific parameters
    without manually writing the key pattern.

    Args:
        *key_params: Parameter names to include in cache key

    Example:
        @cache_key("user_id", "session_id")
        @cached("search:results", ttl=3600)
        async def get_results(user_id: int, session_id: int, extra_param: str):
            # Only user_id and session_id are used in cache key
            # Cache key becomes: "search:results:user_id=1:session_id=2"
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Store key params as function attribute for use by cached()
        func._cache_key_params = key_params  # type: ignore
        return func
    return decorator


def cache_conditional(
    condition: Callable[[Any], bool],
    key_pattern: str,
    ttl: int = 3600,
    namespace: str = "io"
):
    """
    Decorator for conditional caching based on result.

    Only caches the result if condition function returns True.

    Args:
        condition: Function that takes result and returns True to cache
        key_pattern: Cache key pattern with {param} placeholders
        ttl: Time-to-live in seconds (default: 3600 = 1 hour)
        namespace: Cache namespace (default: "io")

    Example:
        @cache_conditional(
            condition=lambda result: len(result) > 0,
            key_pattern="search:results:{query}",
            ttl=3600
        )
        async def search(query: str):
            # Only cache non-empty results
            return results
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Get cache instance
            cache = await get_redis_cache(namespace)

            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            all_kwargs = bound_args.arguments

            # Generate cache key
            try:
                cache_key = key_pattern.format(**all_kwargs)
            except KeyError as e:
                logger.warning(
                    f"Cache key pattern '{key_pattern}' missing parameter: {e}. "
                    "Skipping cache."
                )
                return await func(*args, **kwargs)

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Check condition before caching
            if condition(result):
                await cache.set(cache_key, result, ttl=ttl)
                logger.debug(f"Conditional cache set for {func.__name__}: {cache_key}")
            else:
                logger.debug(f"Conditional cache skipped for {func.__name__}: {cache_key}")

            return result

        return wrapper
    return decorator
