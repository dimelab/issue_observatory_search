"""
Custom exceptions for the Issue Observatory Search application.

This module defines a hierarchy of custom exceptions for better error handling
and consistent error responses throughout the application.
"""
from typing import Optional, Any, Dict
from fastapi import status


class IssueObservatoryException(Exception):
    """
    Base exception for all Issue Observatory errors.

    All custom exceptions should inherit from this class to maintain
    a consistent exception hierarchy.

    Attributes:
        message: Human-readable error message
        error_code: Application-specific error code
        status_code: HTTP status code to return
        details: Additional error details (dict or any serializable type)
    """

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the exception.

        Args:
            message: Human-readable error message
            error_code: Application-specific error code
            status_code: HTTP status code
            details: Additional error details
        """
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


# Authentication & Authorization Exceptions

class AuthenticationError(IssueObservatoryException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid."""

    def __init__(self, message: str = "Invalid username or password"):
        super().__init__(
            message=message,
            details={"hint": "Check your username and password"}
        )


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired."""

    def __init__(self, message: str = "Token has expired"):
        super().__init__(
            message=message,
            details={"hint": "Please log in again"}
        )


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid."""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(message=message)


class AuthorizationError(IssueObservatoryException):
    """Raised when user lacks permission for an operation."""

    def __init__(self, message: str = "Insufficient permissions", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


# Validation Exceptions

class ValidationError(IssueObservatoryException):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        validation_details = details or {}
        if field:
            validation_details["field"] = field

        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=validation_details,
        )


class InvalidInputError(ValidationError):
    """Raised when input data is invalid."""
    pass


class MissingFieldError(ValidationError):
    """Raised when a required field is missing."""

    def __init__(self, field: str):
        super().__init__(
            message=f"Required field '{field}' is missing",
            field=field,
        )


# Resource Exceptions

class ResourceNotFoundError(IssueObservatoryException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str,
        resource_id: Any,
        message: Optional[str] = None,
    ):
        msg = message or f"{resource_type} with ID '{resource_id}' not found"
        super().__init__(
            message=msg,
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": str(resource_id)},
        )


class ResourceAlreadyExistsError(IssueObservatoryException):
    """Raised when attempting to create a resource that already exists."""

    def __init__(
        self,
        resource_type: str,
        identifier: str,
        message: Optional[str] = None,
    ):
        msg = message or f"{resource_type} '{identifier}' already exists"
        super().__init__(
            message=msg,
            error_code="RESOURCE_ALREADY_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
            details={"resource_type": resource_type, "identifier": identifier},
        )


class ResourceConflictError(IssueObservatoryException):
    """Raised when a resource operation conflicts with current state."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="RESOURCE_CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


# Database Exceptions

class DatabaseError(IssueObservatoryException):
    """Base class for database-related errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(self, message: str = "Failed to connect to database"):
        super().__init__(message=message)


class DatabaseTransactionError(DatabaseError):
    """Raised when a database transaction fails."""

    def __init__(self, message: str = "Database transaction failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, details=details)


# External Service Exceptions

class ExternalServiceError(IssueObservatoryException):
    """Raised when an external service call fails."""

    def __init__(
        self,
        service_name: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        msg = message or f"External service '{service_name}' error"
        service_details = details or {}
        service_details["service_name"] = service_name

        super().__init__(
            message=msg,
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=service_details,
        )


class APIRateLimitError(ExternalServiceError):
    """Raised when an external API rate limit is exceeded."""

    def __init__(self, service_name: str, retry_after: Optional[int] = None):
        details = {"retry_after_seconds": retry_after} if retry_after else {}
        super().__init__(
            service_name=service_name,
            message=f"Rate limit exceeded for {service_name}",
            details=details,
        )


class SearchEngineError(ExternalServiceError):
    """Raised when a search engine request fails."""

    def __init__(self, engine_name: str, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            service_name=engine_name,
            message=message or f"Search engine '{engine_name}' error",
            details=details,
        )


class ScrapingError(ExternalServiceError):
    """Raised when web scraping fails."""

    def __init__(self, url: str, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        scraping_details = details or {}
        scraping_details["url"] = url

        super().__init__(
            service_name="WebScraper",
            message=message or f"Failed to scrape URL: {url}",
            details=scraping_details,
        )


# Processing Exceptions

class ProcessingError(IssueObservatoryException):
    """Base class for data processing errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="PROCESSING_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class NLPProcessingError(ProcessingError):
    """Raised when NLP processing fails."""

    def __init__(self, message: str = "NLP processing failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, details=details)


class NetworkGenerationError(ProcessingError):
    """Raised when network generation fails."""

    def __init__(self, message: str = "Network generation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, details=details)


class AnalysisError(ProcessingError):
    """Raised when data analysis fails."""

    def __init__(self, analysis_type: str, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        msg = message or f"{analysis_type} analysis failed"
        analysis_details = details or {}
        analysis_details["analysis_type"] = analysis_type

        super().__init__(message=msg, details=analysis_details)


# Rate Limiting Exceptions

class RateLimitExceededError(IssueObservatoryException):
    """Raised when user exceeds rate limit."""

    def __init__(
        self,
        operation: str,
        limit: int,
        window: str,
        retry_after: Optional[int] = None,
    ):
        details = {
            "operation": operation,
            "limit": limit,
            "window": window,
        }
        if retry_after:
            details["retry_after_seconds"] = retry_after

        super().__init__(
            message=f"Rate limit exceeded for {operation}: {limit} requests per {window}",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


# Configuration Exceptions

class ConfigurationError(IssueObservatoryException):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        details = {"config_key": config_key} if config_key else {}
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class MissingConfigurationError(ConfigurationError):
    """Raised when a required configuration value is missing."""

    def __init__(self, config_key: str):
        super().__init__(
            message=f"Required configuration '{config_key}' is missing",
            config_key=config_key,
        )


# File/Storage Exceptions

class StorageError(IssueObservatoryException):
    """Base class for file storage errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="STORAGE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class FileNotFoundError(StorageError):
    """Raised when a file is not found."""

    def __init__(self, file_path: str):
        super().__init__(
            message=f"File not found: {file_path}",
            details={"file_path": file_path},
        )


class FileUploadError(StorageError):
    """Raised when file upload fails."""

    def __init__(self, message: str = "File upload failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, details=details)


# Task/Job Exceptions

class TaskError(IssueObservatoryException):
    """Base class for Celery task errors."""

    def __init__(self, message: str, task_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        task_details = details or {}
        if task_id:
            task_details["task_id"] = task_id

        super().__init__(
            message=message,
            error_code="TASK_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=task_details,
        )


class TaskNotFoundError(TaskError):
    """Raised when a task is not found."""

    def __init__(self, task_id: str):
        super().__init__(
            message=f"Task not found: {task_id}",
            task_id=task_id,
        )


class TaskTimeoutError(TaskError):
    """Raised when a task times out."""

    def __init__(self, task_id: str, timeout: int):
        super().__init__(
            message=f"Task {task_id} timed out after {timeout} seconds",
            task_id=task_id,
            details={"timeout_seconds": timeout},
        )


# Cache Exceptions

class CacheError(IssueObservatoryException):
    """Base class for cache-related errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CACHE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class CacheConnectionError(CacheError):
    """Raised when cache connection fails."""

    def __init__(self, message: str = "Failed to connect to cache"):
        super().__init__(message=message)
