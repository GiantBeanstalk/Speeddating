"""
Security utilities and functions for the Speed Dating application.
"""

from .csrf import (
    CSRFProtection,
    add_csrf_to_templates,
    csrf_protection,
    generate_csrf_token,
    require_csrf_token,
    validate_csrf_token,
)
from .input_sanitizer import (
    InputSanitizer,
    SanitizationConfig,
    default_sanitizer,
    sanitize_bio,
    sanitize_email,
    sanitize_name,
    sanitize_phone,
    sanitize_search_query,
    sanitize_text,
    validate_uuid,
)
from .super_user import (
    SuperUserManager,
    generate_super_user_secret,
    super_user_manager,
    verify_super_user_secret,
)

__all__ = [
    # Super User
    "SuperUserManager",
    "generate_super_user_secret",
    "super_user_manager",
    "verify_super_user_secret",
    # Input Sanitization
    "InputSanitizer",
    "SanitizationConfig",
    "default_sanitizer",
    "sanitize_bio",
    "sanitize_email",
    "sanitize_name",
    "sanitize_phone",
    "sanitize_search_query",
    "sanitize_text",
    "validate_uuid",
    # CSRF Protection
    "CSRFProtection",
    "add_csrf_to_templates",
    "csrf_protection",
    "generate_csrf_token",
    "require_csrf_token",
    "validate_csrf_token",
]