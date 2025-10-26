#!/usr/bin/env python3
"""Verify installation and create missing files."""
import os
import sys
from pathlib import Path


def verify_directory_structure():
    """Verify all required directories exist."""
    base_dir = Path(__file__).parent.parent
    required_dirs = [
        "backend/core/cache",
        "backend/core/analysis",
        "backend/core/networks",
        "backend/core/nlp",
        "backend/core/scrapers",
        "backend/core/search",
        "backend/core/search_engines",
        "backend/api",
        "backend/models",
        "backend/repositories",
        "backend/schemas",
        "backend/services",
        "backend/tasks",
        "backend/middleware",
        "backend/monitoring",
        "migrations/versions",
        "data/exports",
        "docker",
    ]

    missing_dirs = []
    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        if not full_path.exists():
            missing_dirs.append(dir_path)
            print(f"❌ Missing directory: {dir_path}")
            full_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created: {dir_path}")
        else:
            print(f"✅ Found: {dir_path}")

    return len(missing_dirs) == 0


def create_cache_module():
    """Create cache module files if missing."""
    base_dir = Path(__file__).parent.parent
    cache_dir = base_dir / "backend" / "core" / "cache"

    # Ensure directory exists
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py
    init_file = cache_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text('''"""Redis caching module for performance optimization."""
from backend.core.cache.redis_cache import RedisCache, get_redis_cache
from backend.core.cache.decorators import cached, cache_invalidate

__all__ = [
    "RedisCache",
    "get_redis_cache",
    "cached",
    "cache_invalidate",
]
''')
        print(f"✅ Created: {init_file.relative_to(base_dir)}")

    # Create redis_cache.py
    redis_file = cache_dir / "redis_cache.py"
    if not redis_file.exists():
        redis_file.write_text('''"""Redis cache implementation."""
import json
from typing import Any, Optional
import redis.asyncio as aioredis
from backend.config import settings


class RedisCache:
    """Redis cache manager."""

    def __init__(self):
        """Initialize Redis cache."""
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        self.redis = await aioredis.from_url(
            str(settings.redis_url),
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.redis_max_connections,
        )

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.redis:
            return None
        value = await self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        """Set value in cache with expiration."""
        if not self.redis:
            return
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await self.redis.set(key, serialized, ex=expire)

    async def delete(self, key: str):
        """Delete key from cache."""
        if not self.redis:
            return
        await self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.redis:
            return False
        return bool(await self.redis.exists(key))

    async def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching pattern."""
        if not self.redis:
            return
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)


# Global cache instance
_cache: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    """Get Redis cache instance."""
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache


async def close_redis():
    """Close Redis connection."""
    global _cache
    if _cache:
        await _cache.close()
        _cache = None
''')
        print(f"✅ Created: {redis_file.relative_to(base_dir)}")

    # Create decorators.py
    decorators_file = cache_dir / "decorators.py"
    if not decorators_file.exists():
        decorators_file.write_text('''"""Cache decorators for function caching."""
from functools import wraps
from typing import Callable, Any
import hashlib
import json


def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate cache key from function name and arguments."""
    key_data = {"func": func_name, "args": args, "kwargs": kwargs}
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_string.encode()).hexdigest()
    return f"cache:{func_name}:{key_hash}"


def cached(ttl: int = 3600, key_prefix: str = ""):
    """
    Cache decorator for async functions.

    Args:
        ttl: Time to live in seconds
        key_prefix: Optional prefix for cache key
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from backend.core.cache.redis_cache import get_redis_cache

            cache = get_redis_cache()
            if not cache.redis:
                # Cache not available, execute function
                return await func(*args, **kwargs)

            # Generate cache key
            cache_key = _generate_cache_key(
                f"{key_prefix}{func.__name__}" if key_prefix else func.__name__,
                args,
                kwargs
            )

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, expire=ttl)
            return result

        return wrapper
    return decorator


def cache_invalidate(pattern: str = None, key_func: Callable = None):
    """
    Decorator to invalidate cache after function execution.

    Args:
        pattern: Pattern to match keys for invalidation
        key_func: Function to generate invalidation key from function args
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from backend.core.cache.redis_cache import get_redis_cache

            # Execute function first
            result = await func(*args, **kwargs)

            # Then invalidate cache
            cache = get_redis_cache()
            if cache.redis:
                if key_func:
                    key = key_func(*args, **kwargs)
                    await cache.delete(key)
                elif pattern:
                    await cache.invalidate_pattern(pattern)

            return result

        return wrapper
    return decorator
''')
        print(f"✅ Created: {decorators_file.relative_to(base_dir)}")


def verify_imports():
    """Verify critical imports work."""
    print("\n🔍 Verifying imports...")

    try:
        from backend.config import settings
        print("✅ backend.config")
    except ImportError as e:
        print(f"❌ backend.config: {e}")
        return False

    try:
        from backend.database import engine
        print("✅ backend.database")
    except ImportError as e:
        print(f"❌ backend.database: {e}")
        return False

    try:
        from backend.core.cache.redis_cache import close_redis
        print("✅ backend.core.cache")
    except ImportError as e:
        print(f"❌ backend.core.cache: {e}")
        return False

    try:
        from backend.main import app
        print("✅ backend.main")
    except ImportError as e:
        print(f"❌ backend.main: {e}")
        return False

    return True


def main():
    """Run installation verification."""
    print("=" * 60)
    print("Issue Observatory Search - Installation Verification")
    print("=" * 60)

    print("\n📁 Checking directory structure...")
    verify_directory_structure()

    print("\n📦 Creating missing cache module files...")
    create_cache_module()

    print("\n" + "=" * 60)
    if verify_imports():
        print("\n✅ Installation verified successfully!")
        print("\nYou can now run:")
        print("  python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 3111")
        return 0
    else:
        print("\n❌ Installation verification failed!")
        print("\nPlease check the errors above and run:")
        print("  pip install -e .[dev]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
