"""
Input validation utilities for security.

This module provides comprehensive input validation to prevent injection attacks,
invalid data, and other security vulnerabilities.
"""
import re
from typing import Optional, List, Any, Dict
from urllib.parse import urlparse
import validators
from backend.core.exceptions import ValidationError, InvalidInputError


class InputValidator:
    """
    Input validation utility class.

    Provides methods to validate various types of input data to prevent
    injection attacks, XSS, and other security vulnerabilities.
    """

    # Regex patterns for validation
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,50}$")
    ALPHANUMERIC_PATTERN = re.compile(r"^[a-zA-Z0-9]+$")
    SQL_INJECTION_PATTERNS = [
        re.compile(r"(\bUNION\b|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b)", re.IGNORECASE),
        re.compile(r"(--|;|\/\*|\*\/|xp_|sp_)", re.IGNORECASE),
        re.compile(r"(\bOR\b|\bAND\b)\s+\d+\s*=\s*\d+", re.IGNORECASE),
    ]
    COMMAND_INJECTION_PATTERNS = [
        re.compile(r"[;&|`$()]"),
        re.compile(r"(bash|sh|cmd|powershell|eval|exec)", re.IGNORECASE),
    ]
    XSS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),  # Event handlers like onclick=
        re.compile(r"<iframe[^>]*>", re.IGNORECASE),
    ]

    # Dangerous file extensions
    DANGEROUS_EXTENSIONS = {
        "exe", "bat", "cmd", "com", "pif", "scr", "vbs", "js",
        "jar", "ps1", "sh", "py", "rb", "php", "asp", "aspx",
    }

    # Maximum lengths for common fields
    MAX_USERNAME_LENGTH = 50
    MAX_EMAIL_LENGTH = 254  # RFC 5321
    MAX_PASSWORD_LENGTH = 128
    MAX_URL_LENGTH = 2048
    MAX_SEARCH_QUERY_LENGTH = 500
    MAX_TEXT_LENGTH = 1_000_000  # 1MB
    MAX_FILENAME_LENGTH = 255

    @staticmethod
    def validate_email(email: str) -> str:
        """
        Validate email address.

        Args:
            email: Email address to validate

        Returns:
            Validated and normalized email address

        Raises:
            ValidationError: If email is invalid
        """
        if not email:
            raise ValidationError("Email is required", field="email")

        email = email.strip().lower()

        if len(email) > InputValidator.MAX_EMAIL_LENGTH:
            raise ValidationError(
                f"Email exceeds maximum length of {InputValidator.MAX_EMAIL_LENGTH}",
                field="email",
            )

        if not validators.email(email):
            raise ValidationError("Invalid email format", field="email")

        # Additional domain validation
        domain = email.split("@")[1]
        if not validators.domain(domain):
            raise ValidationError("Invalid email domain", field="email")

        return email

    @staticmethod
    def validate_username(username: str) -> str:
        """
        Validate username.

        Args:
            username: Username to validate

        Returns:
            Validated username

        Raises:
            ValidationError: If username is invalid
        """
        if not username:
            raise ValidationError("Username is required", field="username")

        username = username.strip()

        if len(username) < 3:
            raise ValidationError("Username must be at least 3 characters", field="username")

        if len(username) > InputValidator.MAX_USERNAME_LENGTH:
            raise ValidationError(
                f"Username exceeds maximum length of {InputValidator.MAX_USERNAME_LENGTH}",
                field="username",
            )

        if not InputValidator.USERNAME_PATTERN.match(username):
            raise ValidationError(
                "Username can only contain letters, numbers, hyphens, and underscores",
                field="username",
            )

        return username

    @staticmethod
    def validate_password(password: str) -> None:
        """
        Validate password strength.

        Args:
            password: Password to validate

        Raises:
            ValidationError: If password doesn't meet requirements
        """
        if not password:
            raise ValidationError("Password is required", field="password")

        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters", field="password")

        if len(password) > InputValidator.MAX_PASSWORD_LENGTH:
            raise ValidationError(
                f"Password exceeds maximum length of {InputValidator.MAX_PASSWORD_LENGTH}",
                field="password",
            )

        # Check for complexity requirements
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

        if not (has_upper and has_lower and has_digit):
            raise ValidationError(
                "Password must contain uppercase, lowercase, and numeric characters",
                field="password",
            )

    @staticmethod
    def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> str:
        """
        Validate URL.

        Args:
            url: URL to validate
            allowed_schemes: List of allowed URL schemes (default: ['http', 'https'])

        Returns:
            Validated URL

        Raises:
            ValidationError: If URL is invalid
        """
        if not url:
            raise ValidationError("URL is required", field="url")

        url = url.strip()

        if len(url) > InputValidator.MAX_URL_LENGTH:
            raise ValidationError(
                f"URL exceeds maximum length of {InputValidator.MAX_URL_LENGTH}",
                field="url",
            )

        # Validate URL format
        if not validators.url(url):
            raise ValidationError("Invalid URL format", field="url")

        # Parse and validate components
        parsed = urlparse(url)

        # Check scheme
        if allowed_schemes is None:
            allowed_schemes = ["http", "https"]

        if parsed.scheme not in allowed_schemes:
            raise ValidationError(
                f"URL scheme must be one of: {', '.join(allowed_schemes)}",
                field="url",
            )

        # Validate domain
        if not parsed.netloc:
            raise ValidationError("URL must have a valid domain", field="url")

        # Check for potentially dangerous patterns
        if any(pattern.search(url) for pattern in InputValidator.XSS_PATTERNS):
            raise ValidationError("URL contains potentially dangerous content", field="url")

        return url

    @staticmethod
    def validate_search_query(query: str) -> str:
        """
        Validate search query.

        Args:
            query: Search query to validate

        Returns:
            Validated search query

        Raises:
            ValidationError: If query is invalid or contains dangerous patterns
        """
        if not query:
            raise ValidationError("Search query is required", field="query")

        query = query.strip()

        if len(query) > InputValidator.MAX_SEARCH_QUERY_LENGTH:
            raise ValidationError(
                f"Search query exceeds maximum length of {InputValidator.MAX_SEARCH_QUERY_LENGTH}",
                field="query",
            )

        # Check for SQL injection patterns
        if InputValidator.contains_sql_injection(query):
            raise InvalidInputError(
                "Search query contains potentially dangerous SQL patterns",
                field="query",
            )

        return query

    @staticmethod
    def validate_filename(filename: str) -> str:
        """
        Validate filename.

        Args:
            filename: Filename to validate

        Returns:
            Validated filename

        Raises:
            ValidationError: If filename is invalid or dangerous
        """
        if not filename:
            raise ValidationError("Filename is required", field="filename")

        filename = filename.strip()

        if len(filename) > InputValidator.MAX_FILENAME_LENGTH:
            raise ValidationError(
                f"Filename exceeds maximum length of {InputValidator.MAX_FILENAME_LENGTH}",
                field="filename",
            )

        # Check for path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValidationError("Filename contains invalid characters", field="filename")

        # Check for dangerous extensions
        extension = filename.split(".")[-1].lower() if "." in filename else ""
        if extension in InputValidator.DANGEROUS_EXTENSIONS:
            raise ValidationError(
                f"File extension '.{extension}' is not allowed",
                field="filename",
            )

        # Check for special characters
        if not re.match(r"^[a-zA-Z0-9._-]+$", filename):
            raise ValidationError(
                "Filename can only contain letters, numbers, dots, hyphens, and underscores",
                field="filename",
            )

        return filename

    @staticmethod
    def validate_integer(
        value: Any,
        field: str,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
    ) -> int:
        """
        Validate integer value.

        Args:
            value: Value to validate
            field: Field name for error messages
            min_value: Minimum allowed value
            max_value: Maximum allowed value

        Returns:
            Validated integer

        Raises:
            ValidationError: If value is invalid
        """
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"'{field}' must be an integer", field=field)

        if min_value is not None and int_value < min_value:
            raise ValidationError(
                f"'{field}' must be at least {min_value}",
                field=field,
            )

        if max_value is not None and int_value > max_value:
            raise ValidationError(
                f"'{field}' must be at most {max_value}",
                field=field,
            )

        return int_value

    @staticmethod
    def validate_float(
        value: Any,
        field: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> float:
        """
        Validate float value.

        Args:
            value: Value to validate
            field: Field name for error messages
            min_value: Minimum allowed value
            max_value: Maximum allowed value

        Returns:
            Validated float

        Raises:
            ValidationError: If value is invalid
        """
        try:
            float_value = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"'{field}' must be a number", field=field)

        if min_value is not None and float_value < min_value:
            raise ValidationError(
                f"'{field}' must be at least {min_value}",
                field=field,
            )

        if max_value is not None and float_value > max_value:
            raise ValidationError(
                f"'{field}' must be at most {max_value}",
                field=field,
            )

        return float_value

    @staticmethod
    def contains_sql_injection(text: str) -> bool:
        """
        Check if text contains SQL injection patterns.

        Args:
            text: Text to check

        Returns:
            True if SQL injection patterns detected, False otherwise
        """
        return any(pattern.search(text) for pattern in InputValidator.SQL_INJECTION_PATTERNS)

    @staticmethod
    def contains_command_injection(text: str) -> bool:
        """
        Check if text contains command injection patterns.

        Args:
            text: Text to check

        Returns:
            True if command injection patterns detected, False otherwise
        """
        return any(pattern.search(text) for pattern in InputValidator.COMMAND_INJECTION_PATTERNS)

    @staticmethod
    def contains_xss(text: str) -> bool:
        """
        Check if text contains XSS patterns.

        Args:
            text: Text to check

        Returns:
            True if XSS patterns detected, False otherwise
        """
        return any(pattern.search(text) for pattern in InputValidator.XSS_PATTERNS)

    @staticmethod
    def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
        """
        Basic text sanitization.

        Args:
            text: Text to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized text

        Raises:
            ValidationError: If text is invalid
        """
        if not text:
            return ""

        text = text.strip()

        if max_length and len(text) > max_length:
            raise ValidationError(
                f"Text exceeds maximum length of {max_length}",
                field="text",
            )

        # Check for dangerous patterns
        if InputValidator.contains_sql_injection(text):
            raise InvalidInputError("Text contains potentially dangerous SQL patterns")

        if InputValidator.contains_xss(text):
            raise InvalidInputError("Text contains potentially dangerous XSS patterns")

        return text

    @staticmethod
    def validate_dict_keys(data: Dict[str, Any], allowed_keys: List[str]) -> None:
        """
        Validate that dictionary only contains allowed keys.

        Args:
            data: Dictionary to validate
            allowed_keys: List of allowed keys

        Raises:
            ValidationError: If dictionary contains invalid keys
        """
        invalid_keys = set(data.keys()) - set(allowed_keys)
        if invalid_keys:
            raise ValidationError(
                f"Invalid keys in request: {', '.join(invalid_keys)}",
                details={"invalid_keys": list(invalid_keys)},
            )

    @staticmethod
    def validate_pagination(
        page: int,
        per_page: int,
        max_per_page: int = 500,
    ) -> tuple[int, int]:
        """
        Validate pagination parameters.

        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            max_per_page: Maximum allowed items per page

        Returns:
            Tuple of (validated_page, validated_per_page)

        Raises:
            ValidationError: If parameters are invalid
        """
        page = InputValidator.validate_integer(page, "page", min_value=1)
        per_page = InputValidator.validate_integer(
            per_page,
            "per_page",
            min_value=1,
            max_value=max_per_page,
        )

        return page, per_page
