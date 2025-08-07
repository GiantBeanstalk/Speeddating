"""
Input sanitization utilities for preventing injection attacks.

Provides comprehensive text sanitization, validation, and filtering to prevent
SQL injection, XSS, and other input-based attacks.
"""

import re

import bleach
from pydantic import BaseModel, Field


class SanitizationConfig(BaseModel):
    """Configuration for input sanitization."""

    # HTML sanitization
    allowed_tags: list[str] = Field(default_factory=lambda: [])
    allowed_attributes: dict[str, list[str]] = Field(default_factory=dict)
    strip_html: bool = True

    # Text processing
    max_length: int | None = None
    min_length: int | None = None
    strip_whitespace: bool = True
    normalize_unicode: bool = True

    # Character filtering
    allow_unicode: bool = True
    allow_special_chars: bool = True
    forbidden_patterns: list[str] = Field(default_factory=list)

    # SQL injection protection
    block_sql_keywords: bool = True
    block_sql_operators: bool = True


class InputSanitizer:
    """Comprehensive input sanitization for web applications."""

    # Common SQL injection patterns
    SQL_KEYWORDS = {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "UNION",
        "FROM",
        "WHERE",
        "JOIN",
        "HAVING",
        "GROUP",
        "ORDER",
        "EXEC",
        "EXECUTE",
        "SCRIPT",
        "DECLARE",
        "CAST",
        "CONVERT",
        "INFORMATION_SCHEMA",
        "sys",
        "master",
        "msdb",
    }

    # SQL operators and injection indicators
    SQL_OPERATORS = {
        "--",
        "/*",
        "*/",
        ";",
        "||",
        "&&",
        "xp_",
        "sp_",
        "fn_",
        "@@",
        "0x",
        "char(",
        "nchar(",
        "varchar(",
        "nvarchar(",
        "waitfor",
        "benchmark(",
        "sleep(",
        "pg_sleep(",
    }

    # XSS patterns
    XSS_PATTERNS = [
        r"<script[\s\S]*?</script>",
        r"<iframe[\s\S]*?</iframe>",
        r"javascript:",
        r"vbscript:",
        r"onload\s*=",
        r"onerror\s*=",
        r"onclick\s*=",
        r"onmouseover\s*=",
        r"eval\s*\(",
        r"expression\s*\(",
        r"url\s*\(",
        r"@import",
    ]

    def __init__(self, config: SanitizationConfig | None = None):
        """Initialize sanitizer with configuration."""
        self.config = config or SanitizationConfig()

    def sanitize_text(self, text: str) -> str:
        """
        Comprehensive text sanitization.

        Args:
            text: Input text to sanitize

        Returns:
            Sanitized text safe for database storage and display
        """
        if not isinstance(text, str):
            return str(text)

        # Strip whitespace
        if self.config.strip_whitespace:
            text = text.strip()

        # Length validation
        if self.config.max_length and len(text) > self.config.max_length:
            text = text[: self.config.max_length]

        if self.config.min_length and len(text) < self.config.min_length:
            raise ValueError(
                f"Input too short (min {self.config.min_length} characters)"
            )

        # Unicode normalization
        if self.config.normalize_unicode:
            import unicodedata

            text = unicodedata.normalize("NFKC", text)

        # HTML sanitization
        if self.config.strip_html:
            text = bleach.clean(
                text,
                tags=self.config.allowed_tags,
                attributes=self.config.allowed_attributes,
                strip=True,
            )

        # Remove dangerous patterns
        text = self._remove_dangerous_patterns(text)

        # SQL injection protection
        if self.config.block_sql_keywords or self.config.block_sql_operators:
            self._check_sql_injection(text)

        # Custom forbidden patterns
        for pattern in self.config.forbidden_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                raise ValueError(f"Input contains forbidden pattern: {pattern}")

        return text

    def sanitize_email(self, email: str) -> str:
        """
        Sanitize and validate email address.

        Args:
            email: Email address to sanitize

        Returns:
            Sanitized email address
        """
        if not isinstance(email, str):
            raise ValueError("Email must be a string")

        email = email.strip().lower()

        # Basic email pattern validation
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise ValueError("Invalid email format")

        # Check for dangerous patterns
        if any(pattern in email for pattern in ["..", "@.", ".@", "@@"]):
            raise ValueError("Invalid email format")

        # Length limits
        if len(email) > 254:  # RFC 5321 limit
            raise ValueError("Email address too long")

        return email

    def sanitize_name(self, name: str) -> str:
        """
        Sanitize person name fields.

        Args:
            name: Name to sanitize

        Returns:
            Sanitized name
        """
        config = SanitizationConfig(
            max_length=100,
            min_length=1,
            strip_html=True,
            block_sql_keywords=True,
            block_sql_operators=True,
            forbidden_patterns=[
                r"[<>]",  # No angle brackets
                r"[{}]",  # No curly braces
                r"[\[\]]",  # No square brackets
                r"[|]",  # No pipes
                r"[\\]",  # No backslashes
            ],
        )

        sanitizer = InputSanitizer(config)
        name = sanitizer.sanitize_text(name)

        # Only allow letters, spaces, hyphens, and apostrophes
        if not re.match(r"^[a-zA-ZÀ-ÿ\s\-'\.]+$", name):
            raise ValueError("Name contains invalid characters")

        return name.title()  # Proper case

    def sanitize_bio(self, bio: str) -> str:
        """
        Sanitize biography/profile text.

        Args:
            bio: Biography text to sanitize

        Returns:
            Sanitized bio text
        """
        config = SanitizationConfig(
            max_length=500,
            strip_html=True,
            allowed_tags=["p", "br", "strong", "em", "u"],
            block_sql_keywords=True,
            block_sql_operators=True,
        )

        sanitizer = InputSanitizer(config)
        return sanitizer.sanitize_text(bio)

    def sanitize_search_query(self, query: str) -> str:
        """
        Sanitize search query input.

        Args:
            query: Search query to sanitize

        Returns:
            Sanitized search query
        """
        config = SanitizationConfig(
            max_length=200,
            strip_html=True,
            block_sql_keywords=True,
            block_sql_operators=True,
            forbidden_patterns=[
                r"[<>]",
                r"[{}]",
                r"javascript:",
                r"vbscript:",
            ],
        )

        sanitizer = InputSanitizer(config)
        return sanitizer.sanitize_text(query)

    def _remove_dangerous_patterns(self, text: str) -> str:
        """Remove known dangerous patterns from text."""
        # XSS protection
        for pattern in self.XSS_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # Remove null bytes
        text = text.replace("\x00", "")

        # Remove other control characters
        text = re.sub(r"[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

        return text

    def _check_sql_injection(self, text: str):
        """Check for SQL injection patterns."""
        text_upper = text.upper()

        # Check SQL keywords
        if self.config.block_sql_keywords:
            for keyword in self.SQL_KEYWORDS:
                # Look for keyword boundaries to avoid false positives
                pattern = r"\b" + re.escape(keyword) + r"\b"
                if re.search(pattern, text_upper):
                    raise ValueError(f"Input contains SQL keyword: {keyword}")

        # Check SQL operators
        if self.config.block_sql_operators:
            for operator in self.SQL_OPERATORS:
                if operator in text:
                    raise ValueError(f"Input contains SQL operator: {operator}")

    def validate_uuid(self, uuid_str: str) -> str:
        """
        Validate and sanitize UUID strings.

        Args:
            uuid_str: UUID string to validate

        Returns:
            Validated UUID string
        """
        import uuid

        try:
            # This will raise ValueError if invalid
            uuid_obj = uuid.UUID(uuid_str)
            return str(uuid_obj)
        except (ValueError, TypeError):
            raise ValueError("Invalid UUID format")

    def sanitize_phone(self, phone: str) -> str:
        """
        Sanitize phone number.

        Args:
            phone: Phone number to sanitize

        Returns:
            Sanitized phone number
        """
        if not isinstance(phone, str):
            raise ValueError("Phone must be a string")

        # Remove all non-digit characters except + at the start
        phone = re.sub(r"[^\d+]", "", phone)

        # Ensure + is only at the beginning
        if "+" in phone[1:]:
            raise ValueError("Invalid phone number format")

        # Basic length validation
        if len(phone) < 10 or len(phone) > 15:
            raise ValueError("Phone number length invalid")

        return phone


# Global sanitizer instance
default_sanitizer = InputSanitizer()


# Convenience functions
def sanitize_text(text: str, config: SanitizationConfig | None = None) -> str:
    """Sanitize text with optional custom configuration."""
    sanitizer = InputSanitizer(config) if config else default_sanitizer
    return sanitizer.sanitize_text(text)


def sanitize_email(email: str) -> str:
    """Sanitize email address."""
    return default_sanitizer.sanitize_email(email)


def sanitize_name(name: str) -> str:
    """Sanitize person name."""
    return default_sanitizer.sanitize_name(name)


def sanitize_bio(bio: str) -> str:
    """Sanitize biography text."""
    return default_sanitizer.sanitize_bio(bio)


def sanitize_search_query(query: str) -> str:
    """Sanitize search query."""
    return default_sanitizer.sanitize_search_query(query)


def validate_uuid(uuid_str: str) -> str:
    """Validate UUID string."""
    return default_sanitizer.validate_uuid(uuid_str)


def sanitize_phone(phone: str) -> str:
    """Sanitize phone number."""
    return default_sanitizer.sanitize_phone(phone)
