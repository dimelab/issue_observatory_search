"""
Prometheus metrics for monitoring application performance.

This module defines custom metrics for tracking:
- API request duration and counts
- Search operations
- Scraping operations
- Analysis operations
- Network generation
- Cache performance
- Database connection pool stats
"""
import time
import logging
from typing import Callable, Optional
from functools import wraps
from contextlib import contextmanager

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ============================================================================
# Application Info
# ============================================================================

app_info = Info("app", "Application information")


# ============================================================================
# HTTP Metrics
# ============================================================================

# Request duration histogram (in seconds)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Request counter
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

# Active requests gauge
http_requests_active = Gauge(
    "http_requests_active",
    "Number of active HTTP requests",
    ["method", "endpoint"],
)

# Request size histogram (in bytes)
http_request_size_bytes = Histogram(
    "http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "endpoint"],
    buckets=(100, 1000, 10000, 100000, 1000000, 10000000),
)

# Response size histogram (in bytes)
http_response_size_bytes = Histogram(
    "http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint", "status_code"],
    buckets=(100, 1000, 10000, 100000, 1000000, 10000000),
)


# ============================================================================
# Search Metrics
# ============================================================================

search_operations_total = Counter(
    "search_operations_total",
    "Total search operations",
    ["engine", "status"],
)

search_duration_seconds = Histogram(
    "search_duration_seconds",
    "Search operation duration in seconds",
    ["engine"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

search_results_count = Histogram(
    "search_results_count",
    "Number of search results returned",
    ["engine"],
    buckets=(0, 1, 5, 10, 20, 50, 100),
)


# ============================================================================
# Scraping Metrics
# ============================================================================

scraping_operations_total = Counter(
    "scraping_operations_total",
    "Total scraping operations",
    ["status"],
)

scraping_duration_seconds = Histogram(
    "scraping_duration_seconds",
    "Scraping operation duration in seconds",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

scraping_content_size_bytes = Histogram(
    "scraping_content_size_bytes",
    "Size of scraped content in bytes",
    buckets=(1000, 10000, 100000, 1000000, 10000000),
)

scraping_errors_total = Counter(
    "scraping_errors_total",
    "Total scraping errors",
    ["error_type"],
)


# ============================================================================
# Analysis Metrics
# ============================================================================

analysis_operations_total = Counter(
    "analysis_operations_total",
    "Total analysis operations",
    ["analysis_type", "status"],
)

analysis_duration_seconds = Histogram(
    "analysis_duration_seconds",
    "Analysis operation duration in seconds",
    ["analysis_type"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
)

nlp_processing_tokens = Histogram(
    "nlp_processing_tokens",
    "Number of tokens processed by NLP",
    ["language"],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000),
)


# ============================================================================
# Network Generation Metrics
# ============================================================================

network_generation_total = Counter(
    "network_generation_total",
    "Total network generation operations",
    ["status"],
)

network_generation_duration_seconds = Histogram(
    "network_generation_duration_seconds",
    "Network generation duration in seconds",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)

network_nodes_count = Histogram(
    "network_nodes_count",
    "Number of nodes in generated network",
    buckets=(10, 50, 100, 500, 1000, 5000, 10000),
)

network_edges_count = Histogram(
    "network_edges_count",
    "Number of edges in generated network",
    buckets=(10, 100, 500, 1000, 5000, 10000, 50000),
)


# ============================================================================
# Cache Metrics
# ============================================================================

cache_operations_total = Counter(
    "cache_operations_total",
    "Total cache operations",
    ["operation", "status"],
)

cache_hit_rate = Gauge(
    "cache_hit_rate",
    "Cache hit rate (hits / total requests)",
    ["cache_key_prefix"],
)

cache_duration_seconds = Histogram(
    "cache_duration_seconds",
    "Cache operation duration in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)


# ============================================================================
# Database Metrics
# ============================================================================

db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections",
)

db_connections_pool_size = Gauge(
    "db_connections_pool_size",
    "Database connection pool size",
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

db_operations_total = Counter(
    "db_operations_total",
    "Total database operations",
    ["operation", "status"],
)


# ============================================================================
# Celery Task Metrics
# ============================================================================

celery_tasks_total = Counter(
    "celery_tasks_total",
    "Total Celery tasks",
    ["task_name", "status"],
)

celery_task_duration_seconds = Histogram(
    "celery_task_duration_seconds",
    "Celery task duration in seconds",
    ["task_name"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0),
)

celery_tasks_active = Gauge(
    "celery_tasks_active",
    "Number of active Celery tasks",
    ["task_name"],
)


# ============================================================================
# Business Metrics
# ============================================================================

users_active = Gauge(
    "users_active",
    "Number of active users",
)

searches_per_user = Histogram(
    "searches_per_user",
    "Number of searches per user",
    buckets=(1, 5, 10, 20, 50, 100, 200),
)

sessions_total = Counter(
    "sessions_total",
    "Total number of search sessions created",
)


# ============================================================================
# Helper Functions and Decorators
# ============================================================================

@contextmanager
def track_duration(histogram: Histogram, *labels):
    """
    Context manager to track operation duration.

    Usage:
        with track_duration(search_duration_seconds, "google"):
            # perform search operation
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        histogram.labels(*labels).observe(duration)


def track_search_operation(engine: str):
    """
    Decorator to track search operations.

    Usage:
        @track_search_operation("google")
        async def search(query: str):
            # search implementation
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                # Track result count if result is a list
                if isinstance(result, list):
                    search_results_count.labels(engine=engine).observe(len(result))
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                search_duration_seconds.labels(engine=engine).observe(duration)
                search_operations_total.labels(engine=engine, status=status).inc()

        return wrapper
    return decorator


def track_scraping_operation(func: Callable):
    """
    Decorator to track scraping operations.

    Usage:
        @track_scraping_operation
        async def scrape_url(url: str):
            # scraping implementation
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        status = "success"

        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            status = "error"
            error_type = type(e).__name__
            scraping_errors_total.labels(error_type=error_type).inc()
            raise
        finally:
            duration = time.time() - start_time
            scraping_duration_seconds.observe(duration)
            scraping_operations_total.labels(status=status).inc()

    return wrapper


def track_analysis_operation(analysis_type: str):
    """
    Decorator to track analysis operations.

    Usage:
        @track_analysis_operation("nlp")
        async def analyze_text(text: str):
            # analysis implementation
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                analysis_duration_seconds.labels(analysis_type=analysis_type).observe(duration)
                analysis_operations_total.labels(analysis_type=analysis_type, status=status).inc()

        return wrapper
    return decorator


def track_network_generation(func: Callable):
    """
    Decorator to track network generation operations.

    Usage:
        @track_network_generation
        async def generate_network(session_id: int):
            # network generation implementation
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        status = "success"

        try:
            result = await func(*args, **kwargs)

            # Track network statistics if result has them
            if hasattr(result, "node_count"):
                network_nodes_count.observe(result.node_count)
            if hasattr(result, "edge_count"):
                network_edges_count.observe(result.edge_count)

            return result
        except Exception as e:
            status = "error"
            raise
        finally:
            duration = time.time() - start_time
            network_generation_duration_seconds.observe(duration)
            network_generation_total.labels(status=status).inc()

    return wrapper


# ============================================================================
# Middleware for HTTP Metrics
# ============================================================================

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically track HTTP request metrics.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and track metrics.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response from handler
        """
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        # Get method and path
        method = request.method
        path = self._get_path_template(request)

        # Track active requests
        http_requests_active.labels(method=method, endpoint=path).inc()

        # Track request size
        content_length = request.headers.get("content-length")
        if content_length:
            http_request_size_bytes.labels(method=method, endpoint=path).observe(int(content_length))

        # Track request duration
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code

            # Track response size
            if hasattr(response, "body") and response.body:
                http_response_size_bytes.labels(
                    method=method,
                    endpoint=path,
                    status_code=status_code,
                ).observe(len(response.body))

            return response

        except Exception as e:
            status_code = 500
            raise

        finally:
            # Track duration
            duration = time.time() - start_time
            http_request_duration_seconds.labels(
                method=method,
                endpoint=path,
                status_code=status_code,
            ).observe(duration)

            # Track request count
            http_requests_total.labels(
                method=method,
                endpoint=path,
                status_code=status_code,
            ).inc()

            # Decrement active requests
            http_requests_active.labels(method=method, endpoint=path).dec()

    @staticmethod
    def _get_path_template(request: Request) -> str:
        """
        Get the path template for the request (e.g., /api/users/{user_id}).

        Args:
            request: FastAPI request

        Returns:
            Path template or actual path
        """
        # Try to get the route path template
        if hasattr(request, "scope") and "route" in request.scope:
            route = request.scope["route"]
            if hasattr(route, "path"):
                return route.path

        # Fallback to actual path
        return request.url.path


def setup_metrics(app) -> None:
    """
    Setup metrics middleware and initialize application info.

    Args:
        app: FastAPI application instance
    """
    # Add metrics middleware
    app.add_middleware(MetricsMiddleware)

    # Set application info
    app_info.info({
        "version": "0.1.0",
        "name": "Issue Observatory Search",
    })

    logger.info("Metrics middleware configured")


def get_metrics() -> bytes:
    """
    Get current metrics in Prometheus format.

    Returns:
        Metrics in Prometheus text format
    """
    return generate_latest()


def get_metrics_content_type() -> str:
    """
    Get the content type for Prometheus metrics.

    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST
