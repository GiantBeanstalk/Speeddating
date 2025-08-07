"""
Cross-Site Request Forgery (CSRF) protection utilities.

Provides CSRF token generation, validation, and middleware integration
for form-based requests.
"""

import hashlib
import hmac
import secrets
import time
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.templating import Jinja2Templates

from app.config import settings


class CSRFProtection:
    """CSRF protection implementation."""
    
    def __init__(self, secret_key: Optional[str] = None, token_lifetime: int = 3600):
        """
        Initialize CSRF protection.
        
        Args:
            secret_key: Secret key for token generation
            token_lifetime: Token lifetime in seconds (default 1 hour)
        """
        self.secret_key = secret_key or settings.get("SECRET_KEY", "default-secret-key")
        self.token_lifetime = token_lifetime
    
    def generate_token(self, session_id: Optional[str] = None) -> str:
        """
        Generate a CSRF token.
        
        Args:
            session_id: Optional session identifier
            
        Returns:
            CSRF token string
        """
        # Create timestamp
        timestamp = str(int(time.time()))
        
        # Create random component
        random_part = secrets.token_urlsafe(16)
        
        # Create session component
        session_part = session_id or "anonymous"
        
        # Combine components
        token_data = f"{timestamp}:{random_part}:{session_part}"
        
        # Create HMAC signature
        signature = hmac.new(
            self.secret_key.encode(),
            token_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Return token as timestamp:random:session:signature
        return f"{timestamp}:{random_part}:{session_part}:{signature}"
    
    def validate_token(self, token: str, session_id: Optional[str] = None) -> bool:
        """
        Validate a CSRF token.
        
        Args:
            token: CSRF token to validate
            session_id: Expected session identifier
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            parts = token.split(':')
            if len(parts) != 4:
                return False
            
            timestamp_str, random_part, token_session, provided_signature = parts
            
            # Check timestamp
            token_time = int(timestamp_str)
            current_time = int(time.time())
            
            if current_time - token_time > self.token_lifetime:
                return False  # Token expired
            
            # Check session if provided
            expected_session = session_id or "anonymous"
            if token_session != expected_session:
                return False
            
            # Recreate token data
            token_data = f"{timestamp_str}:{random_part}:{token_session}"
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.secret_key.encode(),
                token_data.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Use constant-time comparison
            return hmac.compare_digest(provided_signature, expected_signature)
            
        except (ValueError, IndexError):
            return False
    
    def get_token_from_request(self, request: Request) -> Optional[str]:
        """
        Extract CSRF token from request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            CSRF token if found, None otherwise
        """
        # Check form data
        if hasattr(request, 'form'):
            form = getattr(request, 'form', {})
            if 'csrf_token' in form:
                return form['csrf_token']
        
        # Check headers
        if 'X-CSRF-Token' in request.headers:
            return request.headers['X-CSRF-Token']
        
        return None
    
    def require_csrf_token(self, request: Request, session_id: Optional[str] = None) -> None:
        """
        Require and validate CSRF token from request.
        
        Args:
            request: FastAPI request object
            session_id: Expected session identifier
            
        Raises:
            HTTPException: If CSRF token is missing or invalid
        """
        token = self.get_token_from_request(request)
        
        if not token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing"
            )
        
        if not self.validate_token(token, session_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token invalid"
            )


# Global CSRF protection instance
csrf_protection = CSRFProtection()


def generate_csrf_token(session_id: Optional[str] = None) -> str:
    """Generate a CSRF token."""
    return csrf_protection.generate_token(session_id)


def validate_csrf_token(token: str, session_id: Optional[str] = None) -> bool:
    """Validate a CSRF token."""
    return csrf_protection.validate_token(token, session_id)


def require_csrf_token(request: Request, session_id: Optional[str] = None) -> None:
    """Require and validate CSRF token from request."""
    csrf_protection.require_csrf_token(request, session_id)


def add_csrf_to_templates(templates: Jinja2Templates) -> None:
    """
    Add CSRF token generation to Jinja2 templates.
    
    Args:
        templates: Jinja2Templates instance
    """
    def csrf_token(session_id: Optional[str] = None) -> str:
        """Template function to generate CSRF token."""
        return generate_csrf_token(session_id)
    
    # Add the function to template globals
    templates.env.globals['csrf_token'] = csrf_token