"""Main FastAPI application."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db, close_db, engine
from backend.core.cache.redis_cache import close_redis
from backend.middleware import setup_rate_limiting, setup_db_profiler
from backend.middleware.error_handler import setup_exception_handlers
from backend.monitoring.metrics import setup_metrics, get_metrics, get_metrics_content_type
from backend.monitoring.health import HealthCheck, liveness_check, readiness_check, startup_check
from backend.api import auth, admin, search, scraping, analysis, networks, frontend, partials


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    await init_db()

    # Setup database profiler (slow query logging)
    if settings.query_slow_threshold > 0:
        setup_db_profiler(engine)

    yield

    # Shutdown
    await close_db()
    await close_redis()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Web application for mapping issues through web searches and content analysis",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip compression for responses > 1KB
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # Only compress responses larger than 1KB
    compresslevel=6,  # Balance between speed and compression ratio
)

# Setup rate limiting
if settings.rate_limit_enabled:
    setup_rate_limiting(app)

# Setup monitoring and metrics
setup_metrics(app)

# Setup exception handlers
setup_exception_handlers(app)

# Mount static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Include API routers
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(admin.router, prefix=settings.api_v1_prefix)
app.include_router(search.router, prefix=settings.api_v1_prefix)
app.include_router(scraping.router, prefix=settings.api_v1_prefix)
app.include_router(analysis.router, prefix=settings.api_v1_prefix)
app.include_router(networks.router, prefix=settings.api_v1_prefix)

# Include HTML partial routes (for HTMX)
app.include_router(partials.router)

# Include frontend routes (HTML templates)
app.include_router(frontend.router)


@app.get("/health")
async def health_check() -> dict:
    """
    Basic health check endpoint.

    Returns:
        Basic health status
    """
    return {
        "status": "healthy",
        "environment": settings.environment,
    }


@app.get("/health/live")
async def health_live() -> dict:
    """
    Kubernetes liveness probe endpoint.

    Indicates if the application is running.

    Returns:
        Liveness status
    """
    return await liveness_check()


@app.get("/health/ready")
async def health_ready() -> dict:
    """
    Kubernetes readiness probe endpoint.

    Indicates if the application is ready to serve traffic.

    Returns:
        Readiness status
    """
    return await readiness_check()


@app.get("/health/startup")
async def health_startup() -> dict:
    """
    Kubernetes startup probe endpoint.

    Indicates if the application has started successfully.

    Returns:
        Startup status
    """
    return await startup_check()


@app.get("/health/detail")
async def health_detail() -> dict:
    """
    Detailed health check endpoint.

    Checks all application components and their status.

    Returns:
        Detailed health status for all components
    """
    return await HealthCheck.check_all()


@app.get("/metrics")
async def metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Returns:
        Metrics in Prometheus text format
    """
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type(),
    )
