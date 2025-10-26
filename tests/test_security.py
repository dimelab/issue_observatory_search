"""
Tests for security validation and sanitization.

Tests cover:
- Input validation (SQL injection, XSS, command injection)
- Output sanitization
- Error handling
- Authentication/authorization
"""
import pytest
from backend.security.validator import InputValidator
from backend.security.sanitizer import OutputSanitizer
from backend.core.exceptions import ValidationError, InvalidInputError


class TestInputValidator:
    """Tests for InputValidator class."""

    def test_validate_email_valid(self):
        """Test valid email validation."""
        email = "user@example.com"
        result = InputValidator.validate_email(email)
        assert result == "user@example.com"

    def test_validate_email_invalid(self):
        """Test invalid email validation."""
        with pytest.raises(ValidationError):
            InputValidator.validate_email("invalid-email")

    def test_validate_email_too_long(self):
        """Test email too long."""
        long_email = "a" * 300 + "@example.com"
        with pytest.raises(ValidationError):
            InputValidator.validate_email(long_email)

    def test_validate_username_valid(self):
        """Test valid username."""
        username = "valid_user123"
        result = InputValidator.validate_username(username)
        assert result == "valid_user123"

    def test_validate_username_too_short(self):
        """Test username too short."""
        with pytest.raises(ValidationError):
            InputValidator.validate_username("ab")

    def test_validate_username_invalid_chars(self):
        """Test username with invalid characters."""
        with pytest.raises(ValidationError):
            InputValidator.validate_username("user@name")

    def test_validate_password_valid(self):
        """Test valid password."""
        InputValidator.validate_password("StrongPass123")

    def test_validate_password_too_short(self):
        """Test password too short."""
        with pytest.raises(ValidationError):
            InputValidator.validate_password("Short1")

    def test_validate_password_no_uppercase(self):
        """Test password without uppercase."""
        with pytest.raises(ValidationError):
            InputValidator.validate_password("weakpass123")

    def test_validate_url_valid(self):
        """Test valid URL."""
        url = "https://example.com/path"
        result = InputValidator.validate_url(url)
        assert "example.com" in result

    def test_validate_url_invalid_scheme(self):
        """Test URL with invalid scheme."""
        with pytest.raises(ValidationError):
            InputValidator.validate_url("javascript:alert(1)")

    def test_validate_url_too_long(self):
        """Test URL too long."""
        long_url = "https://example.com/" + "a" * 3000
        with pytest.raises(ValidationError):
            InputValidator.validate_url(long_url)

    def test_contains_sql_injection(self):
        """Test SQL injection detection."""
        assert InputValidator.contains_sql_injection("SELECT * FROM users")
        assert InputValidator.contains_sql_injection("1' OR '1'='1")
        assert not InputValidator.contains_sql_injection("normal search query")

    def test_contains_xss(self):
        """Test XSS detection."""
        assert InputValidator.contains_xss("<script>alert('XSS')</script>")
        assert InputValidator.contains_xss("<iframe src='evil.com'>")
        assert not InputValidator.contains_xss("normal text")

    def test_validate_search_query_sql_injection(self):
        """Test search query with SQL injection attempt."""
        with pytest.raises(InvalidInputError):
            InputValidator.validate_search_query("test' OR '1'='1")

    def test_validate_filename_path_traversal(self):
        """Test filename with path traversal."""
        with pytest.raises(ValidationError):
            InputValidator.validate_filename("../../etc/passwd")

    def test_validate_filename_dangerous_extension(self):
        """Test filename with dangerous extension."""
        with pytest.raises(ValidationError):
            InputValidator.validate_filename("malware.exe")

    def test_validate_integer_valid(self):
        """Test integer validation."""
        result = InputValidator.validate_integer("42", "count")
        assert result == 42

    def test_validate_integer_invalid(self):
        """Test invalid integer."""
        with pytest.raises(ValidationError):
            InputValidator.validate_integer("not_a_number", "count")

    def test_validate_integer_range(self):
        """Test integer range validation."""
        with pytest.raises(ValidationError):
            InputValidator.validate_integer("150", "percentage", min_value=0, max_value=100)


class TestOutputSanitizer:
    """Tests for OutputSanitizer class."""

    def test_sanitize_html(self):
        """Test HTML sanitization."""
        dangerous_html = "<script>alert('XSS')</script>Hello"
        result = OutputSanitizer.sanitize_html(dangerous_html)
        assert "<script>" not in result
        assert "alert" not in result

    def test_sanitize_text(self):
        """Test text sanitization."""
        text = "<b>Bold</b> & special chars"
        result = OutputSanitizer.sanitize_text(text)
        assert "&lt;b&gt;" in result
        assert "&amp;" in result

    def test_remove_sensitive_fields(self):
        """Test removal of sensitive fields."""
        data = {
            "username": "user",
            "password": "secret123",
            "api_key": "key123",
            "public_data": "visible",
        }
        result = OutputSanitizer.remove_sensitive_fields(data)
        assert result["username"] == "user"
        assert result["password"] == "***REDACTED***"
        assert result["api_key"] == "***REDACTED***"
        assert result["public_data"] == "visible"

    def test_remove_sensitive_fields_nested(self):
        """Test removal of sensitive fields in nested structures."""
        data = {
            "user": {
                "name": "John",
                "password": "secret",
            },
            "items": [
                {"id": 1, "secret_key": "key123"},
            ],
        }
        result = OutputSanitizer.remove_sensitive_fields(data)
        assert result["user"]["password"] == "***REDACTED***"
        assert result["items"][0]["secret_key"] == "***REDACTED***"

    def test_mask_email(self):
        """Test email masking."""
        email = "john.doe@example.com"
        result = OutputSanitizer.mask_email(email)
        assert result.startswith("j***e@")
        assert "@example.com" in result

    def test_mask_string(self):
        """Test string masking."""
        secret = "1234567890"
        result = OutputSanitizer.mask_string(secret, visible_chars=2)
        assert result.startswith("12")
        assert result.endswith("90")
        assert "**" in result

    def test_sanitize_filename_for_download(self):
        """Test filename sanitization for downloads."""
        filename = "../../malicious file.exe"
        result = OutputSanitizer.sanitize_filename_for_download(filename)
        assert ".." not in result
        assert "/" not in result
        assert " " not in result
