"""
Global error handler middleware for FastAPI.

Provides consistent error responses and logging for all exceptions.
"""
import logging
import traceback
from typing import Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.core.exceptions import IssueObservatoryException
from backend.config import settings
from backend.security.sanitizer import OutputSanitizer

logger = logging.getLogger(__name__)


async def issue_observatory_exception_handler(
    request: Request,
    exc: IssueObservatoryException,
) -> JSONResponse:
    """
    Handle custom Issue Observatory exceptions.

    Args:
        request: FastAPI request object
        exc: Custom exception

    Returns:
        JSONResponse with error details
    """
    # Log the error with context
    logger.error(
        f"Issue Observatory Error: {exc.error_code}",
        extra={
            "error_code": exc.error_code,
            "message": exc.message,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else None,
        },
    )

    # Build error response
    error_response = {
        "error": {
            "code": exc.error_code,
            "message": exc.message,
            "status_code": exc.status_code,
        }
    }

    # Add details if available (only in debug mode for sensitive errors)
    if exc.details:
        if settings.debug or exc.status_code < 500:
            error_response["error"]["details"] = exc.details

    # Add request ID if available
    request_id = request.headers.get("X-Request-ID")
    if request_id:
        error_response["error"]["request_id"] = request_id

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """
    Handle HTTP exceptions from Starlette/FastAPI.

    Args:
        request: FastAPI request object
        exc: HTTP exception

    Returns:
        JSONResponse with error details
    """
    # Log non-404 errors
    if exc.status_code != status.HTTP_404_NOT_FOUND:
        logger.warning(
            f"HTTP Exception: {exc.status_code}",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "path": request.url.path,
                "method": request.method,
                "client": request.client.host if request.client else None,
            },
        )

    error_response = {
        "error": {
            "code": "HTTP_ERROR",
            "message": exc.detail,
            "status_code": exc.status_code,
        }
    }

    # Add request ID if available
    request_id = request.headers.get("X-Request-ID")
    if request_id:
        error_response["error"]["request_id"] = request_id

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle request validation errors from Pydantic.

    Args:
        request: FastAPI request object
        exc: Validation exception

    Returns:
        JSONResponse with validation error details
    """
    # Extract validation errors
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })

    logger.warning(
        "Validation Error",
        extra={
            "errors": errors,
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else None,
        },
    )

    error_response = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "details": {
                "validation_errors": errors,
            },
        }
    }

    # Add request ID if available
    request_id = request.headers.get("X-Request-ID")
    if request_id:
        error_response["error"]["request_id"] = request_id

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response,
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle all uncaught exceptions.

    Args:
        request: FastAPI request object
        exc: Any exception

    Returns:
        JSONResponse with error details
    """
    # Log the full exception with traceback
    logger.error(
        "Unhandled Exception",
        extra={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else None,
        },
        exc_info=True,  # This includes the full traceback
    )

    # Sanitize error message
    error_data = OutputSanitizer.sanitize_error_message(exc, debug=settings.debug)

    error_response = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }
    }

    # In debug mode, include exception details
    if settings.debug:
        error_response["error"]["debug"] = {
            "exception_type": error_data["error_type"],
            "exception_message": error_data["message"],
            "traceback": traceback.format_exc(),
        }

    # Add request ID if available
    request_id = request.headers.get("X-Request-ID")
    if request_id:
        error_response["error"]["request_id"] = request_id

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response,
    )


def setup_exception_handlers(app) -> None:
    """
    Register all exception handlers with the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    # Custom exception handlers
    app.add_exception_handler(IssueObservatoryException, issue_observatory_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Exception handlers registered")
