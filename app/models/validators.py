"""
Enhanced Pydantic validators with security-focused validation.

Provides custom validators for various data types with built-in sanitization
and security checks to prevent injection attacks.
"""

import re
import uuid
from typing import Any

from pydantic import field_validator, ValidationInfo

from app.security import (
    sanitize_bio,
    sanitize_email,
    sanitize_name,
    sanitize_phone,
    sanitize_search_query,
    sanitize_text,
    validate_uuid,
)


class SecureValidators:
    """Collection of secure Pydantic field validators."""
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Any) -> str:
        """Validate and sanitize email addresses."""
        if not isinstance(v, str):
            raise ValueError('Email must be a string')
        return sanitize_email(v)
    
    @field_validator('first_name', 'last_name', 'display_name')
    @classmethod
    def validate_name(cls, v: Any) -> str:
        """Validate and sanitize name fields."""
        if not isinstance(v, str):
            raise ValueError('Name must be a string')
        return sanitize_name(v)
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Any) -> str:
        """Validate and sanitize phone numbers."""
        if not isinstance(v, str):
            raise ValueError('Phone must be a string')
        return sanitize_phone(v)
    
    @field_validator('bio', 'public_bio', 'description')
    @classmethod
    def validate_bio(cls, v: Any) -> str:
        """Validate and sanitize bio/description fields."""
        if not isinstance(v, str):
            raise ValueError('Bio must be a string')
        return sanitize_bio(v)
    
    @field_validator('name', 'title', 'location')
    @classmethod
    def validate_general_text(cls, v: Any) -> str:
        """Validate and sanitize general text fields."""
        if not isinstance(v, str):
            raise ValueError('Text field must be a string')
        return sanitize_text(v)
    
    @field_validator('search_query', 'query')
    @classmethod
    def validate_search_query(cls, v: Any) -> str:
        """Validate and sanitize search queries."""
        if not isinstance(v, str):
            raise ValueError('Query must be a string')
        return sanitize_search_query(v)
    
    @field_validator('id', 'user_id', 'event_id', 'attendee_id', 'match_id', 'round_id')
    @classmethod
    def validate_uuid_field(cls, v: Any) -> str:
        """Validate UUID fields."""
        if isinstance(v, uuid.UUID):
            return str(v)
        if not isinstance(v, str):
            raise ValueError('UUID must be a string')
        return validate_uuid(v)
    
    @field_validator('fetlife_username')
    @classmethod
    def validate_fetlife_username(cls, v: Any) -> str:
        """Validate FetLife usernames."""
        if not isinstance(v, str):
            raise ValueError('FetLife username must be a string')
        
        # Remove @ prefix if present
        username = v.lstrip('@')
        
        # Sanitize as general text first
        username = sanitize_text(username)
        
        # FetLife username pattern validation
        if not re.match(r'^[a-zA-Z0-9_-]{3,20}$', username):
            raise ValueError(
                'FetLife username must be 3-20 characters and contain only '
                'letters, numbers, underscores, and hyphens'
            )
        
        return username
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Any, info: ValidationInfo) -> str:
        """Validate password strength."""
        if not isinstance(v, str):
            raise ValueError('Password must be a string')
        
        # Basic length check
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if len(v) > 128:
            raise ValueError('Password must be less than 128 characters long')
        
        # Check for common patterns that might indicate injection attempts
        dangerous_patterns = [
            r'<script',
            r'javascript:',
            r'vbscript:',
            r'onload=',
            r'onerror=',
            r'eval\(',
            r'expression\(',
        ]
        
        password_lower = v.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, password_lower):
                raise ValueError('Password contains invalid characters')
        
        # Don't sanitize passwords as they need to be preserved exactly
        # but do check for null bytes and control characters
        if '\x00' in v or any(ord(c) < 32 for c in v if c not in '\t\n\r'):
            raise ValueError('Password contains invalid characters')
        
        return v
    
    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: Any) -> str:
        """Validate currency codes."""
        if not isinstance(v, str):
            raise ValueError('Currency must be a string')
        
        v = v.upper().strip()
        
        # Basic ISO 4217 currency code validation
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError('Currency must be a 3-letter ISO code')
        
        # Common currency codes (extend as needed)
        valid_currencies = {
            'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'CNY', 'SEK', 'NOK',
            'DKK', 'PLN', 'CZK', 'HUF', 'NZD', 'SGD', 'HKD', 'MXN', 'BRL', 'INR'
        }
        
        if v not in valid_currencies:
            raise ValueError(f'Unsupported currency code: {v}')
        
        return v
    
    @field_validator('tags', 'categories')
    @classmethod
    def validate_string_list(cls, v: Any) -> list[str]:
        """Validate lists of strings."""
        if not isinstance(v, list):
            raise ValueError('Must be a list')
        
        validated_items = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError('All items must be strings')
            validated_items.append(sanitize_text(item))
        
        return validated_items
    
    @field_validator('notes', 'comments')
    @classmethod
    def validate_notes(cls, v: Any) -> str:
        """Validate note/comment fields."""
        if not isinstance(v, str):
            raise ValueError('Notes must be a string')
        
        # Allow longer text but still sanitize
        from app.security.input_sanitizer import InputSanitizer, SanitizationConfig
        
        config = SanitizationConfig(
            max_length=2000,
            strip_html=True,
            block_sql_keywords=True,
            block_sql_operators=True,
        )
        
        sanitizer = InputSanitizer(config)
        return sanitizer.sanitize_text(v)
    
    @field_validator('url', 'website')
    @classmethod
    def validate_url(cls, v: Any) -> str:
        """Validate URL fields."""
        if not isinstance(v, str):
            raise ValueError('URL must be a string')
        
        v = v.strip()
        
        # Basic URL pattern validation
        url_pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/[^\s]*)?$'
        if not re.match(url_pattern, v):
            raise ValueError('Invalid URL format')
        
        # Check for dangerous patterns
        dangerous_patterns = [
            'javascript:',
            'vbscript:',
            'data:',
            'file:',
            'ftp:',
        ]
        
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in v_lower:
                raise ValueError('URL scheme not allowed')
        
        # Length limit
        if len(v) > 500:
            raise ValueError('URL too long')
        
        return v