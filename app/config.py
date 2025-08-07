"""
Configuration management using Dynaconf with comprehensive validation.
"""

import re

from dynaconf import Dynaconf, Validator


def validate_database_url(value: str) -> bool:
    """Validate database URL format."""
    if not value:
        return False

    # Basic SQLAlchemy URL pattern validation
    patterns = [
        r"^sqlite\+aiosqlite:///.*\.db$",  # SQLite
        r"^postgresql\+asyncpg://.*",  # PostgreSQL
        r"^mysql\+aiomysql://.*",  # MySQL
    ]

    return any(re.match(pattern, value) for pattern in patterns)


def validate_email_address(value: str | None) -> bool:
    """Validate email address format."""
    if not value:
        return True  # Optional field

    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(email_pattern, value))


def validate_url_list(value: list) -> bool:
    """Validate list of URLs."""
    if not isinstance(value, list):
        return False

    url_pattern = r"^https?://.*|^\*$"  # Allow * for development
    return all(re.match(url_pattern, str(url)) for url in value)


def validate_port(value: int) -> bool:
    """Validate port number."""
    return isinstance(value, int) and 1 <= value <= 65535


# Core application validators
core_validators = [
    # Security settings
    Validator(
        "SECRET_KEY",
        must_exist=True,
        len_min=32,
        messages={
            "must_exist_true": "SECRET_KEY is required for security",
            "len_min": "SECRET_KEY must be at least 32 characters for security",
        },
    ),
    # Database configuration
    Validator(
        "DATABASE_URL",
        default="sqlite+aiosqlite:///./speed_dating.db",
        condition=validate_database_url,
        messages={"condition": "DATABASE_URL must be a valid SQLAlchemy URL"},
    ),
    # Server settings
    Validator("DEBUG", default=False, is_type_of=bool),
    Validator("DATABASE_ECHO", default=False, is_type_of=bool),
    Validator("HOST", default="127.0.0.1", is_type_of=str),
    Validator(
        "PORT",
        default=8000,
        is_type_of=int,
        condition=validate_port,
        messages={"condition": "PORT must be between 1 and 65535"},
    ),
    # CORS settings
    Validator(
        "ALLOWED_ORIGINS",
        default=["http://localhost:3000", "http://localhost:8000"],
        is_type_of=list,
        condition=validate_url_list,
        messages={"condition": "ALLOWED_ORIGINS must be a list of valid URLs"},
    ),
    # Application-specific settings
    Validator("QR_CODE_BASE_URL", default="http://localhost:8000", is_type_of=str),
    Validator("PDF_BADGES_PER_PAGE", default=35, is_type_of=int, gte=1, lte=100),
    # Documentation settings
    Validator("DOCS_DIRECTORY", default="docs", is_type_of=str),
    Validator("AUTO_GENERATE_DOCS", default=True, is_type_of=bool),
]

# Email/SMTP validators (optional for password reset)
email_validators = [
    Validator(
        "SMTP_HOST", is_type_of=str, when=Validator("SMTP_USERNAME", must_exist=True)
    ),
    Validator("SMTP_PORT", default=587, is_type_of=int, condition=validate_port),
    Validator("SMTP_USERNAME", is_type_of=str),
    Validator("SMTP_PASSWORD", is_type_of=str),
    Validator("SMTP_TLS", default=True, is_type_of=bool),
    Validator(
        "SMTP_FROM_EMAIL",
        default="noreply@speeddating.app",
        is_type_of=str,
        condition=validate_email_address,
        messages={"condition": "SMTP_FROM_EMAIL must be a valid email address"},
    ),
]

# Combine core and email validators (production validation handled at runtime)
all_validators = core_validators + email_validators

settings = Dynaconf(
    envvar_prefix="SPEEDDATING",
    settings_files=["settings.toml", ".secrets.toml"],
    environments=True,
    load_dotenv=True,
    validators=all_validators,
    validate=True,  # Validate on access
)
