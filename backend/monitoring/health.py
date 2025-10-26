"""
Health check endpoints for monitoring application status.

Provides detailed health checks for:
- Database connectivity
- Redis/Cache connectivity
- Celery workers
- External services (optional)
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import engine
from backend.core.cache.redis_cache import get_redis_client
from backend.config import settings

logger = logging.getLogger(__name__)


class HealthStatus:
    """Health status constants."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class HealthCheck:
    """
    Health check utility class.

    Provides methods to check the health of various application components.
    """

    @staticmethod
    async def check_database() -> Dict[str, Any]:
        """
        Check database connectivity and performance.

        Returns:
            Dictionary with database health status
        """
        start_time = datetime.now()
        status = HealthStatus.HEALTHY
        details = {}

        try:
            # Test database connection with a simple query
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                await result.fetchone()

            # Calculate response time
            response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            details["response_time_ms"] = round(response_time_ms, 2)

            # Check connection pool stats
            pool = engine.pool
            details["pool_size"] = pool.size()
            details["checked_in_connections"] = pool.checkedin()
            details["checked_out_connections"] = pool.checkedout()
            details["overflow_connections"] = pool.overflow()

            # Mark as degraded if response time is high
            if response_time_ms > 1000:
                status = HealthStatus.DEGRADED
                details["warning"] = "Database response time is high"

            # Mark as degraded if pool is nearly exhausted
            if pool.checkedout() > pool.size() * 0.8:
                status = HealthStatus.DEGRADED
                details["warning"] = "Database connection pool nearly exhausted"

        except Exception as e:
            status = HealthStatus.UNHEALTHY
            details["error"] = str(e)
            logger.error(f"Database health check failed: {e}")

        return {
            "status": status,
            "details": details,
        }

    @staticmethod
    async def check_redis() -> Dict[str, Any]:
        """
        Check Redis connectivity and performance.

        Returns:
            Dictionary with Redis health status
        """
        start_time = datetime.now()
        status = HealthStatus.HEALTHY
        details = {}

        try:
            # Get Redis client
            redis = await get_redis_client()

            # Test Redis connection with ping
            pong = await redis.ping()

            if not pong:
                raise Exception("Redis ping failed")

            # Calculate response time
            response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            details["response_time_ms"] = round(response_time_ms, 2)

            # Get Redis info
            info = await redis.info()
            details["connected_clients"] = info.get("connected_clients", 0)
            details["used_memory_human"] = info.get("used_memory_human", "unknown")
            details["redis_version"] = info.get("redis_version", "unknown")

            # Mark as degraded if response time is high
            if response_time_ms > 500:
                status = HealthStatus.DEGRADED
                details["warning"] = "Redis response time is high"

        except Exception as e:
            status = HealthStatus.UNHEALTHY
            details["error"] = str(e)
            logger.error(f"Redis health check failed: {e}")

        return {
            "status": status,
            "details": details,
        }

    @staticmethod
    async def check_celery() -> Dict[str, Any]:
        """
        Check Celery worker availability.

        Returns:
            Dictionary with Celery health status
        """
        status = HealthStatus.HEALTHY
        details = {}

        try:
            from backend.celery_app import celery_app

            # Inspect active workers
            inspect = celery_app.control.inspect()

            # Get active workers with timeout
            active = inspect.active(timeout=2.0)
            stats = inspect.stats(timeout=2.0)

            if not active:
                status = HealthStatus.UNHEALTHY
                details["error"] = "No active Celery workers found"
            else:
                details["active_workers"] = len(active)
                details["workers"] = list(active.keys())

                # Get worker statistics
                if stats:
                    total_tasks = sum(
                        worker_stats.get("total", {}).values()
                        for worker_stats in stats.values()
                    )
                    details["total_tasks_processed"] = total_tasks

        except ImportError:
            status = HealthStatus.DEGRADED
            details["warning"] = "Celery not configured"
        except Exception as e:
            status = HealthStatus.DEGRADED
            details["error"] = str(e)
            details["warning"] = "Could not connect to Celery workers"
            logger.warning(f"Celery health check failed: {e}")

        return {
            "status": status,
            "details": details,
        }

    @staticmethod
    async def check_disk_space() -> Dict[str, Any]:
        """
        Check available disk space.

        Returns:
            Dictionary with disk space health status
        """
        status = HealthStatus.HEALTHY
        details = {}

        try:
            import shutil

            # Check disk usage
            usage = shutil.disk_usage("/")

            total_gb = usage.total / (1024 ** 3)
            used_gb = usage.used / (1024 ** 3)
            free_gb = usage.free / (1024 ** 3)
            percent_used = (usage.used / usage.total) * 100

            details["total_gb"] = round(total_gb, 2)
            details["used_gb"] = round(used_gb, 2)
            details["free_gb"] = round(free_gb, 2)
            details["percent_used"] = round(percent_used, 2)

            # Mark as degraded if disk is more than 80% full
            if percent_used > 80:
                status = HealthStatus.DEGRADED
                details["warning"] = "Disk space is low"

            # Mark as unhealthy if disk is more than 95% full
            if percent_used > 95:
                status = HealthStatus.UNHEALTHY
                details["error"] = "Disk space critically low"

        except Exception as e:
            status = HealthStatus.DEGRADED
            details["error"] = str(e)
            logger.warning(f"Disk space check failed: {e}")

        return {
            "status": status,
            "details": details,
        }

    @staticmethod
    async def check_all() -> Dict[str, Any]:
        """
        Run all health checks.

        Returns:
            Dictionary with overall health status and individual component statuses
        """
        # Run all health checks concurrently
        results = await asyncio.gather(
            HealthCheck.check_database(),
            HealthCheck.check_redis(),
            HealthCheck.check_celery(),
            HealthCheck.check_disk_space(),
            return_exceptions=True,
        )

        # Parse results
        database_health = results[0] if not isinstance(results[0], Exception) else {
            "status": HealthStatus.UNHEALTHY,
            "details": {"error": str(results[0])},
        }

        redis_health = results[1] if not isinstance(results[1], Exception) else {
            "status": HealthStatus.UNHEALTHY,
            "details": {"error": str(results[1])},
        }

        celery_health = results[2] if not isinstance(results[2], Exception) else {
            "status": HealthStatus.UNHEALTHY,
            "details": {"error": str(results[2])},
        }

        disk_health = results[3] if not isinstance(results[3], Exception) else {
            "status": HealthStatus.UNHEALTHY,
            "details": {"error": str(results[3])},
        }

        # Determine overall status
        all_statuses = [
            database_health["status"],
            redis_health["status"],
            celery_health["status"],
            disk_health["status"],
        ]

        if HealthStatus.UNHEALTHY in all_statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in all_statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "environment": settings.environment,
            "version": settings.app_version,
            "checks": {
                "database": database_health,
                "redis": redis_health,
                "celery": celery_health,
                "disk": disk_health,
            },
        }


async def liveness_check() -> Dict[str, Any]:
    """
    Liveness check - indicates if the application is running.

    This should be a simple check that returns quickly.
    Kubernetes will restart the pod if this fails.

    Returns:
        Dictionary with liveness status
    """
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat(),
    }


async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check - indicates if the application is ready to serve traffic.

    This checks if critical dependencies (database, cache) are available.
    Kubernetes will not route traffic to the pod if this fails.

    Returns:
        Dictionary with readiness status
    """
    # Check critical dependencies
    database_health = await HealthCheck.check_database()
    redis_health = await HealthCheck.check_redis()

    # Application is ready only if database and redis are healthy
    is_ready = (
        database_health["status"] == HealthStatus.HEALTHY
        and redis_health["status"] == HealthStatus.HEALTHY
    )

    status = "ready" if is_ready else "not_ready"

    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "database": database_health,
            "redis": redis_health,
        },
    }


async def startup_check() -> Dict[str, Any]:
    """
    Startup check - indicates if the application has started successfully.

    This can take longer than liveness/readiness checks.
    Kubernetes will wait for this before starting liveness/readiness probes.

    Returns:
        Dictionary with startup status
    """
    # Run full health check
    health = await HealthCheck.check_all()

    is_started = health["status"] != HealthStatus.UNHEALTHY

    return {
        "status": "started" if is_started else "not_started",
        "timestamp": datetime.now().isoformat(),
        "health": health,
    }
