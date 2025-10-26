"""Rate limiting middleware using slowapi."""
import logging
from typing import Callable
from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from backend.config import settings

logger = logging.getLogger(__name__)


def get_identifier(request: Request) -> str:
    """
    Get identifier for rate limiting.

    Uses remote address by default, but can be extended to use
    user ID or API key for authenticated requests.

    Args:
        request: FastAPI request

    Returns:
        Identifier string for rate limiting
    """
    # For authenticated requests, prefer user ID
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"

    # Fall back to IP address
    return get_remote_address(request)


# Create limiter instance
limiter = Limiter(
    key_func=get_identifier,
    storage_uri=str(settings.redis_url),
    strategy="fixed-window",
    default_limits=[
        f"{settings.rate_limit_per_minute}/minute"
    ],
    headers_enabled=True,
)


def setup_rate_limiting(app: FastAPI) -> None:
    """
    Configure rate limiting for FastAPI app.

    Adds:
    - Rate limit state to app
    - Exception handler for rate limit exceeded
    - Response headers with rate limit info

    Args:
        app: FastAPI application instance
    """
    # Add limiter to app state
    app.state.limiter = limiter

    # Add exception handler
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Add middleware for rate limit headers
    @app.middleware("http")
    async def add_rate_limit_headers(
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Add rate limit headers to all responses.

        Headers:
        - X-RateLimit-Limit: Maximum requests allowed
        - X-RateLimit-Remaining: Requests remaining
        - X-RateLimit-Reset: Time when limit resets
        """
        response = await call_next(request)

        # Get rate limit info from limiter
        try:
            limit_key = limiter.key_func(request)
            limit_info = limiter.limiter.get_window_stats(
                limit_key,
                f"{settings.rate_limit_per_minute}/minute"
            )

            if limit_info:
                response.headers["X-RateLimit-Limit"] = str(
                    settings.rate_limit_per_minute
                )
                response.headers["X-RateLimit-Remaining"] = str(
                    limit_info.remaining
                )
                response.headers["X-RateLimit-Reset"] = str(
                    limit_info.reset_time
                )
        except Exception as e:
            logger.debug(f"Failed to add rate limit headers: {e}")

        return response

    logger.info(
        f"Rate limiting configured: {settings.rate_limit_per_minute}/minute"
    )


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded
) -> Response:
    """
    Custom handler for rate limit exceeded errors.

    Returns 429 Too Many Requests with helpful message.

    Args:
        request: Request that exceeded rate limit
        exc: RateLimitExceeded exception

    Returns:
        JSON response with error details
    """
    from fastapi.responses import JSONResponse

    logger.warning(
        f"Rate limit exceeded for {get_identifier(request)} "
        f"on {request.url.path}"
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please slow down.",
                "detail": str(exc.detail),
            }
        },
        headers={
            "Retry-After": str(exc.detail.split()[-1])
            if "seconds" in str(exc.detail) else "60"
        }
    )
