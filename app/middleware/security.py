"""
Security middleware for request processing and protection.

Provides comprehensive request sanitization, rate limiting, and security headers.
"""

import json
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any
from urllib.parse import unquote

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.security.input_sanitizer import (
    InputSanitizer,
    default_sanitizer,
)

# Configure logging
logger = logging.getLogger(__name__)

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware for comprehensive request protection.

    Features:
    - Input sanitization for all text inputs
    - SQL injection protection
    - XSS prevention
    - Rate limiting per IP and endpoint
    - Security headers injection
    - Suspicious activity logging
    """

    def __init__(
        self,
        app,
        sanitizer: InputSanitizer = None,
        enable_sanitization: bool = True,
        enable_rate_limiting: bool = True,
        enable_security_headers: bool = True,
        log_suspicious_activity: bool = True,
        max_request_size: int = 1024 * 1024,  # 1MB
    ):
        """
        Initialize security middleware.

        Args:
            app: FastAPI application instance
            sanitizer: Input sanitizer instance
            enable_sanitization: Enable input sanitization
            enable_rate_limiting: Enable rate limiting
            enable_security_headers: Add security headers
            log_suspicious_activity: Log suspicious requests
            max_request_size: Maximum request size in bytes
        """
        super().__init__(app)
        self.sanitizer = sanitizer or default_sanitizer
        self.enable_sanitization = enable_sanitization
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_security_headers = enable_security_headers
        self.log_suspicious_activity = log_suspicious_activity
        self.max_request_size = max_request_size

        # Suspicious activity tracking
        self.suspicious_ips: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "first_seen": time.time(),
                "last_seen": time.time(),
                "patterns": set(),
            }
        )

        # Rate limiting counters
        self.request_counts: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "window_start": time.time()}
        )

        # Sensitive endpoints that need extra protection
        self.sensitive_endpoints = {
            "/auth/jwt/login",
            "/auth/register",
            "/setup/super-user",
            "/api/events",
            "/api/attendees",
            "/api/profiles",
        }

        # Exempt endpoints from sanitization
        self.sanitization_exempt = {
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security middleware."""
        start_time = time.time()

        try:
            # Check request size
            if hasattr(request, "content_length") and request.content_length:
                if request.content_length > self.max_request_size:
                    logger.warning(
                        f"Request too large: {request.content_length} bytes from {request.client.host}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": "Request too large"},
                    )

            # Rate limiting check
            if self.enable_rate_limiting:
                if not await self._check_rate_limit(request):
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "Too many requests"},
                    )

            # Input sanitization
            if (
                self.enable_sanitization
                and request.url.path not in self.sanitization_exempt
            ):
                try:
                    await self._sanitize_request(request)
                except ValueError as e:
                    logger.warning(
                        f"Sanitization failed for {request.url.path}: {str(e)}"
                    )
                    if self.log_suspicious_activity:
                        await self._log_suspicious_activity(
                            request, f"sanitization_failed: {str(e)}"
                        )

                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"detail": "Invalid input data"},
                    )

            # Process request
            response = await call_next(request)

            # Add security headers
            if self.enable_security_headers:
                response = await self._add_security_headers(response)

            # Log processing time for monitoring
            processing_time = time.time() - start_time
            if processing_time > 5.0:  # Log slow requests
                logger.info(
                    f"Slow request: {request.url.path} took {processing_time:.2f}s"
                )

            return response

        except Exception as e:
            logger.error(f"Security middleware error: {str(e)}")
            if self.log_suspicious_activity:
                await self._log_suspicious_activity(
                    request, f"middleware_error: {str(e)}"
                )

            # Let the error propagate to FastAPI's error handlers
            raise

    async def _check_rate_limit(self, request: Request) -> bool:
        """
        Check rate limiting for the request.

        Returns:
            True if request is allowed, False if rate limited
        """
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Different limits for different endpoint types
        if request.url.path in self.sensitive_endpoints:
            limit = 5  # requests per minute for sensitive endpoints
            window = 60
        elif request.method in ["POST", "PUT", "DELETE"]:
            limit = 20  # requests per minute for write operations
            window = 60
        else:
            limit = 100  # requests per minute for read operations
            window = 60

        # Check rate limit
        key = f"{client_ip}:{request.url.path}"
        request_data = self.request_counts[key]

        # Reset window if needed
        if current_time - request_data["window_start"] > window:
            request_data["count"] = 0
            request_data["window_start"] = current_time

        # Check if limit exceeded
        if request_data["count"] >= limit:
            if self.log_suspicious_activity:
                await self._log_suspicious_activity(
                    request, f"rate_limit_exceeded: {request_data['count']}"
                )
            return False

        # Increment counter
        request_data["count"] += 1
        return True

    async def _sanitize_request(self, request: Request) -> None:
        """
        Sanitize request data for security.

        Args:
            request: FastAPI request object

        Raises:
            ValueError: If input contains dangerous content
        """
        # Sanitize query parameters
        if request.query_params:
            for key, value in request.query_params.items():
                try:
                    # URL decode first
                    decoded_value = unquote(value)
                    self.sanitizer.sanitize_text(decoded_value)
                except ValueError as e:
                    raise ValueError(f"Query parameter '{key}': {str(e)}")

        # Sanitize path parameters
        if hasattr(request, "path_params") and request.path_params:
            for key, value in request.path_params.items():
                try:
                    if key.endswith("_id") or key == "id":
                        # Validate UUID format for ID parameters
                        self.sanitizer.validate_uuid(str(value))
                    else:
                        self.sanitizer.sanitize_text(str(value))
                except ValueError as e:
                    raise ValueError(f"Path parameter '{key}': {str(e)}")

        # Sanitize form data and JSON body
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")

            if "application/json" in content_type:
                await self._sanitize_json_body(request)
            elif "application/x-www-form-urlencoded" in content_type:
                await self._sanitize_form_data(request)
            elif "multipart/form-data" in content_type:
                await self._sanitize_multipart_data(request)

    async def _sanitize_json_body(self, request: Request) -> None:
        """Sanitize JSON request body."""
        try:
            body = await request.body()
            if body:
                # Parse JSON
                data = json.loads(body)

                # Recursively sanitize all string values
                self._sanitize_dict_values(data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format")
        except Exception as e:
            logger.warning(f"JSON sanitization error: {str(e)}")

    async def _sanitize_form_data(self, request: Request) -> None:
        """Sanitize form data."""
        try:
            form = await request.form()
            for key, value in form.items():
                if isinstance(value, str):
                    if key in ["email"]:
                        self.sanitizer.sanitize_email(value)
                    elif key in ["first_name", "last_name", "display_name"]:
                        self.sanitizer.sanitize_name(value)
                    elif key in ["bio", "public_bio", "description"]:
                        self.sanitizer.sanitize_bio(value)
                    else:
                        self.sanitizer.sanitize_text(value)
        except Exception as e:
            raise ValueError(f"Form data sanitization error: {str(e)}")

    async def _sanitize_multipart_data(self, request: Request) -> None:
        """Sanitize multipart form data."""
        # Similar to form data but handles file uploads
        await self._sanitize_form_data(request)

    def _sanitize_dict_values(self, data: Any) -> None:
        """Recursively sanitize dictionary values."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    # Apply appropriate sanitization based on field name
                    if key in ["email"]:
                        data[key] = self.sanitizer.sanitize_email(value)
                    elif key in ["first_name", "last_name", "display_name"]:
                        data[key] = self.sanitizer.sanitize_name(value)
                    elif key in ["bio", "public_bio", "description"]:
                        data[key] = self.sanitizer.sanitize_bio(value)
                    elif key in ["phone"]:
                        data[key] = self.sanitizer.sanitize_phone(value)
                    elif key.endswith("_id") or key == "id":
                        data[key] = self.sanitizer.validate_uuid(value)
                    else:
                        data[key] = self.sanitizer.sanitize_text(value)
                elif isinstance(value, (dict, list)):
                    self._sanitize_dict_values(value)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    self._sanitize_dict_values(item)

    async def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response."""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' fonts.googleapis.com cdn.tailwindcss.com; font-src 'self' fonts.gstatic.com; img-src 'self' data:; connect-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), location=(), notifications=()",
        }

        for header, value in security_headers.items():
            response.headers[header] = value

        return response

    async def _log_suspicious_activity(self, request: Request, pattern: str) -> None:
        """Log suspicious activity for monitoring."""
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Update suspicious activity tracking
        ip_data = self.suspicious_ips[client_ip]
        ip_data["count"] += 1
        ip_data["last_seen"] = current_time
        ip_data["patterns"].add(pattern)

        # Log the activity
        logger.warning(
            f"Suspicious activity from {client_ip}: {pattern} "
            f"(path: {request.url.path}, method: {request.method}, "
            f"user_agent: {request.headers.get('user-agent', 'unknown')})"
        )

        # If this IP has multiple suspicious activities, log as potential attack
        if ip_data["count"] > 5:
            logger.critical(
                f"Potential attack from {client_ip}: {ip_data['count']} suspicious activities "
                f"over {current_time - ip_data['first_seen']:.0f} seconds. "
                f"Patterns: {list(ip_data['patterns'])}"
            )

    def get_suspicious_ips(self) -> dict[str, dict[str, Any]]:
        """Get dictionary of suspicious IP addresses for monitoring."""
        return dict(self.suspicious_ips)

    def clear_suspicious_ips(self) -> None:
        """Clear suspicious IP tracking (for testing/maintenance)."""
        self.suspicious_ips.clear()


# Rate limit handler
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceptions."""
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )
    return response
