"""
Middleware package for the Speed Dating application.

Provides centralized middleware for security, error handling, and request processing.
"""

from app.middleware.security import SecurityMiddleware

__all__ = ["SecurityMiddleware"]
