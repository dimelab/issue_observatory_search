"""
Output sanitization utilities for security.

This module provides utilities to sanitize output data to prevent XSS attacks,
data leakage, and other security vulnerabilities.
"""
import re
import html
from typing import Any, Dict, Optional, List, Union
from datetime import datetime
from decimal import Decimal


class OutputSanitizer:
    """
    Output sanitization utility class.

    Provides methods to sanitize various types of output data to prevent
    XSS attacks, data leakage, and ensure safe rendering.
    """

    # Fields that should never be exposed in API responses
    SENSITIVE_FIELDS = {
        "password",
        "password_hash",
        "hashed_password",
        "secret",
        "secret_key",
        "api_key",
        "token",
        "access_token",
        "refresh_token",
        "private_key",
        "ssh_key",
        "credit_card",
        "ssn",
        "social_security",
    }

    # HTML tags that are considered safe
    SAFE_HTML_TAGS = {
        "b", "i", "u", "em", "strong", "p", "br", "span",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li",
        "a", "code", "pre",
    }

    # HTML attributes that are considered safe
    SAFE_HTML_ATTRIBUTES = {
        "href", "title", "class", "id", "style",
    }

    @staticmethod
    def sanitize_html(text: str, allowed_tags: Optional[set] = None) -> str:
        """
        Sanitize HTML content by escaping or removing dangerous elements.

        Args:
            text: HTML text to sanitize
            allowed_tags: Set of allowed HTML tags (default: None = escape all)

        Returns:
            Sanitized HTML text
        """
        if not text:
            return ""

        # If no tags are allowed, escape everything
        if allowed_tags is None:
            return html.escape(text)

        # Remove script tags and their content
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)

        # Remove style tags and their content
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)

        # Remove event handlers (onclick, onload, etc.)
        text = re.sub(r"\s+on\w+\s*=\s*[\"'][^\"']*[\"']", "", text, flags=re.IGNORECASE)

        # Remove javascript: protocol
        text = re.sub(r"javascript:", "", text, flags=re.IGNORECASE)

        # Remove data: protocol (can be used for XSS)
        text = re.sub(r"data:", "", text, flags=re.IGNORECASE)

        # For simplicity in production, you might want to use a library like bleach
        # For now, we'll escape everything not in allowed_tags
        return html.escape(text)

    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        Sanitize plain text by escaping HTML entities.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text with HTML entities escaped
        """
        if not text:
            return ""

        return html.escape(str(text))

    @staticmethod
    def sanitize_url(url: str) -> str:
        """
        Sanitize URL to prevent XSS attacks.

        Args:
            url: URL to sanitize

        Returns:
            Sanitized URL
        """
        if not url:
            return ""

        url = str(url).strip()

        # Remove javascript: protocol
        if url.lower().startswith("javascript:"):
            return ""

        # Remove data: protocol
        if url.lower().startswith("data:"):
            return ""

        # Only allow http and https protocols
        if not (url.startswith("http://") or url.startswith("https://")):
            # Assume https if no protocol specified
            url = "https://" + url

        return html.escape(url)

    @staticmethod
    def remove_sensitive_fields(data: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
        """
        Recursively remove sensitive fields from data structures.

        Args:
            data: Data structure (dict, list, or primitive) to sanitize

        Returns:
            Data structure with sensitive fields removed/masked
        """
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # Check if key is sensitive
                if any(sensitive in key.lower() for sensitive in OutputSanitizer.SENSITIVE_FIELDS):
                    sanitized[key] = "***REDACTED***"
                else:
                    sanitized[key] = OutputSanitizer.remove_sensitive_fields(value)
            return sanitized

        elif isinstance(data, list):
            return [OutputSanitizer.remove_sensitive_fields(item) for item in data]

        else:
            return data

    @staticmethod
    def sanitize_error_message(error: Exception, debug: bool = False) -> Dict[str, Any]:
        """
        Sanitize error messages to prevent information leakage.

        Args:
            error: Exception to sanitize
            debug: Whether to include detailed error information

        Returns:
            Sanitized error response dictionary
        """
        error_type = type(error).__name__

        if debug:
            # In debug mode, include full error details
            return {
                "error_type": error_type,
                "message": str(error),
                "traceback": None,  # Could add traceback in future
            }
        else:
            # In production, provide generic error message
            generic_messages = {
                "DatabaseError": "A database error occurred",
                "ConnectionError": "A connection error occurred",
                "TimeoutError": "The operation timed out",
                "ValidationError": str(error),  # Validation errors are safe to expose
                "AuthenticationError": "Authentication failed",
                "AuthorizationError": "Access denied",
            }

            message = generic_messages.get(error_type, "An error occurred")

            return {
                "error_type": "InternalError",
                "message": message,
            }

    @staticmethod
    def sanitize_dict(data: Dict[str, Any], escape_html: bool = True) -> Dict[str, Any]:
        """
        Sanitize all string values in a dictionary.

        Args:
            data: Dictionary to sanitize
            escape_html: Whether to escape HTML in string values

        Returns:
            Sanitized dictionary
        """
        sanitized = {}

        for key, value in data.items():
            # Check if key is sensitive
            if any(sensitive in key.lower() for sensitive in OutputSanitizer.SENSITIVE_FIELDS):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str):
                sanitized[key] = OutputSanitizer.sanitize_text(value) if escape_html else value
            elif isinstance(value, dict):
                sanitized[key] = OutputSanitizer.sanitize_dict(value, escape_html)
            elif isinstance(value, list):
                sanitized[key] = OutputSanitizer.sanitize_list(value, escape_html)
            else:
                sanitized[key] = value

        return sanitized

    @staticmethod
    def sanitize_list(data: List[Any], escape_html: bool = True) -> List[Any]:
        """
        Sanitize all values in a list.

        Args:
            data: List to sanitize
            escape_html: Whether to escape HTML in string values

        Returns:
            Sanitized list
        """
        sanitized = []

        for item in data:
            if isinstance(item, str):
                sanitized.append(OutputSanitizer.sanitize_text(item) if escape_html else item)
            elif isinstance(item, dict):
                sanitized.append(OutputSanitizer.sanitize_dict(item, escape_html))
            elif isinstance(item, list):
                sanitized.append(OutputSanitizer.sanitize_list(item, escape_html))
            else:
                sanitized.append(item)

        return sanitized

    @staticmethod
    def sanitize_json_response(data: Any, remove_sensitive: bool = True) -> Any:
        """
        Sanitize data for JSON API responses.

        Args:
            data: Data to sanitize (dict, list, or primitive)
            remove_sensitive: Whether to remove sensitive fields

        Returns:
            Sanitized data ready for JSON serialization
        """
        # Remove sensitive fields if requested
        if remove_sensitive:
            data = OutputSanitizer.remove_sensitive_fields(data)

        # Convert special types to JSON-serializable formats
        return OutputSanitizer._make_json_serializable(data)

    @staticmethod
    def _make_json_serializable(obj: Any) -> Any:
        """
        Convert objects to JSON-serializable formats.

        Args:
            obj: Object to convert

        Returns:
            JSON-serializable version of object
        """
        if isinstance(obj, dict):
            return {key: OutputSanitizer._make_json_serializable(value) for key, value in obj.items()}

        elif isinstance(obj, list):
            return [OutputSanitizer._make_json_serializable(item) for item in obj]

        elif isinstance(obj, datetime):
            return obj.isoformat()

        elif isinstance(obj, Decimal):
            return float(obj)

        elif isinstance(obj, (bytes, bytearray)):
            return obj.decode("utf-8", errors="replace")

        elif hasattr(obj, "__dict__"):
            # Handle custom objects
            return OutputSanitizer._make_json_serializable(obj.__dict__)

        else:
            return obj

    @staticmethod
    def mask_email(email: str) -> str:
        """
        Mask email address for privacy.

        Args:
            email: Email address to mask

        Returns:
            Masked email address (e.g., u***@example.com)
        """
        if not email or "@" not in email:
            return email

        username, domain = email.split("@", 1)

        if len(username) <= 2:
            masked_username = username[0] + "*"
        else:
            masked_username = username[0] + "***" + username[-1]

        return f"{masked_username}@{domain}"

    @staticmethod
    def mask_string(text: str, visible_chars: int = 4, mask_char: str = "*") -> str:
        """
        Mask a string, showing only first and last few characters.

        Args:
            text: String to mask
            visible_chars: Number of characters to show at start and end
            mask_char: Character to use for masking

        Returns:
            Masked string
        """
        if not text:
            return text

        if len(text) <= visible_chars * 2:
            return mask_char * len(text)

        return (
            text[:visible_chars]
            + mask_char * (len(text) - visible_chars * 2)
            + text[-visible_chars:]
        )

    @staticmethod
    def sanitize_sql_identifier(identifier: str) -> str:
        """
        Sanitize SQL identifier (table/column name).

        Args:
            identifier: SQL identifier to sanitize

        Returns:
            Sanitized identifier

        Raises:
            ValueError: If identifier contains invalid characters
        """
        # Only allow alphanumeric characters and underscores
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
            raise ValueError(f"Invalid SQL identifier: {identifier}")

        # Prevent SQL reserved keywords (basic check)
        sql_keywords = {
            "select", "insert", "update", "delete", "drop", "create",
            "alter", "table", "database", "union", "where", "from",
        }

        if identifier.lower() in sql_keywords:
            raise ValueError(f"SQL reserved keyword not allowed: {identifier}")

        return identifier

    @staticmethod
    def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """
        Truncate text to maximum length with suffix.

        Args:
            text: Text to truncate
            max_length: Maximum length (including suffix)
            suffix: Suffix to append if truncated

        Returns:
            Truncated text
        """
        if not text or len(text) <= max_length:
            return text

        return text[: max_length - len(suffix)] + suffix

    @staticmethod
    def sanitize_filename_for_download(filename: str) -> str:
        """
        Sanitize filename for safe download.

        Args:
            filename: Filename to sanitize

        Returns:
            Sanitized filename safe for Content-Disposition header
        """
        if not filename:
            return "download"

        # Remove path separators
        filename = filename.replace("/", "_").replace("\\", "_")

        # Remove control characters
        filename = "".join(c for c in filename if ord(c) >= 32)

        # Replace spaces with underscores
        filename = filename.replace(" ", "_")

        # Only keep alphanumeric, underscore, hyphen, and dot
        filename = re.sub(r"[^a-zA-Z0-9._-]", "", filename)

        # Ensure filename isn't empty
        if not filename:
            return "download"

        return filename
