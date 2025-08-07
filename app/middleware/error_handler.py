"""
Error handling middleware for consistent error responses and logging.

Provides centralized error handling, logging, and response formatting
for all application errors.
"""

import logging
import traceback
import uuid
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

from app.exceptions import DatabaseError, SpeedDatingException

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for centralized error handling and logging."""

    async def dispatch(self, request: Request, call_next):
        """Process request and handle any errors that occur."""
        # Generate correlation ID for error tracking
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        try:
            response = await call_next(request)
            return response

        except SpeedDatingException as e:
            # Handle custom application exceptions
            logger.warning(
                f"Application error [{correlation_id}]: {e.error_code} - {e.message}",
                extra={
                    "correlation_id": correlation_id,
                    "error_code": e.error_code,
                    "error_details": e.details,
                    "path": request.url.path,
                    "method": request.method,
                    "user_agent": request.headers.get("user-agent"),
                    "ip_address": request.client.host if request.client else None,
                },
            )

            return self._create_error_response(
                status_code=e.status_code,
                error_code=e.error_code,
                message=e.message,
                details=e.details,
                correlation_id=correlation_id,
            )

        except HTTPException as e:
            # Handle FastAPI HTTP exceptions
            logger.info(
                f"HTTP exception [{correlation_id}]: {e.status_code} - {e.detail}",
                extra={
                    "correlation_id": correlation_id,
                    "status_code": e.status_code,
                    "path": request.url.path,
                    "method": request.method,
                },
            )

            # Convert to consistent format
            return self._create_error_response(
                status_code=e.status_code,
                error_code="HTTP_EXCEPTION",
                message=str(e.detail) if e.detail else "HTTP error",
                correlation_id=correlation_id,
            )

        except SQLAlchemyError as e:
            # Handle database errors
            error_msg = "Database operation failed"
            error_code = "DATABASE_ERROR"

            if isinstance(e, IntegrityError):
                error_code = "INTEGRITY_CONSTRAINT_VIOLATION"
                error_msg = "Data integrity constraint violated"
            elif isinstance(e, OperationalError):
                error_code = "DATABASE_OPERATIONAL_ERROR"
                error_msg = "Database operational error"

            logger.error(
                f"Database error [{correlation_id}]: {error_msg} - {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "path": request.url.path,
                    "method": request.method,
                    "error_details": str(e),
                },
            )

            return self._create_error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code=error_code,
                message=error_msg,
                correlation_id=correlation_id,
            )

        except ValueError as e:
            # Handle validation and value errors
            logger.warning(
                f"Value error [{correlation_id}]: {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "path": request.url.path,
                    "method": request.method,
                    "error_details": str(e),
                },
            )

            return self._create_error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="INVALID_VALUE",
                message=str(e),
                correlation_id=correlation_id,
            )

        except PermissionError as e:
            # Handle permission errors
            logger.warning(
                f"Permission error [{correlation_id}]: {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "path": request.url.path,
                    "method": request.method,
                },
            )

            return self._create_error_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="PERMISSION_DENIED",
                message="Permission denied",
                correlation_id=correlation_id,
            )

        except Exception as e:
            # Handle unexpected errors
            logger.error(
                f"Unexpected error [{correlation_id}]: {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__,
                    "path": request.url.path,
                    "method": request.method,
                    "traceback": traceback.format_exc(),
                },
            )

            # Don't expose internal error details in production
            return self._create_error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred",
                correlation_id=correlation_id,
            )

    def _create_error_response(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> JSONResponse:
        """Create standardized error response."""
        error_response = {
            "error": {
                "code": error_code,
                "message": message,
                "correlation_id": correlation_id,
                "timestamp": self._get_timestamp(),
            }
        }

        if details:
            error_response["error"]["details"] = details

        return JSONResponse(
            status_code=status_code,
            content=error_response,
            headers={
                "X-Correlation-ID": correlation_id or "unknown",
                "Content-Type": "application/json",
            },
        )

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import UTC, datetime

        return datetime.now(UTC).isoformat()


def create_database_error_from_exception(
    e: SQLAlchemyError, operation: str = None, table: str = None
) -> DatabaseError:
    """Convert SQLAlchemy exception to DatabaseError."""
    if isinstance(e, IntegrityError):
        message = "Data integrity constraint violated"
        if "UNIQUE constraint failed" in str(e):
            message = "Duplicate entry - record already exists"
        elif "NOT NULL constraint failed" in str(e):
            message = "Required field cannot be empty"
        elif "FOREIGN KEY constraint failed" in str(e):
            message = "Referenced record does not exist"
    elif isinstance(e, OperationalError):
        message = "Database connection or operational error"
    else:
        message = "Database operation failed"

    return DatabaseError(message=message, operation=operation, table=table)


def handle_validation_errors(errors: list) -> dict[str, Any]:
    """Convert pydantic validation errors to structured format."""
    formatted_errors = []

    for error in errors:
        formatted_error = {
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }

        if "input" in error:
            formatted_error["invalid_value"] = str(error["input"])

        formatted_errors.append(formatted_error)

    return {"validation_errors": formatted_errors, "error_count": len(formatted_errors)}


class ErrorLogger:
    """Utility class for structured error logging."""

    @staticmethod
    def log_business_error(
        operation: str,
        error: str,
        context: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ):
        """Log business logic errors."""
        logger.warning(
            f"Business error in {operation}: {error}",
            extra={
                "operation": operation,
                "error_type": "business_logic",
                "context": context or {},
                "correlation_id": correlation_id,
            },
        )

    @staticmethod
    def log_security_event(
        event_type: str,
        description: str,
        user_id: str | None = None,
        ip_address: str | None = None,
        correlation_id: str | None = None,
    ):
        """Log security-related events."""
        logger.warning(
            f"Security event - {event_type}: {description}",
            extra={
                "event_type": event_type,
                "security_event": True,
                "user_id": user_id,
                "ip_address": ip_address,
                "correlation_id": correlation_id,
            },
        )

    @staticmethod
    def log_performance_issue(
        operation: str,
        duration: float,
        threshold: float = 5.0,
        correlation_id: str | None = None,
    ):
        """Log performance issues."""
        if duration > threshold:
            logger.warning(
                f"Performance issue in {operation}: {duration:.2f}s (threshold: {threshold}s)",
                extra={
                    "operation": operation,
                    "duration": duration,
                    "threshold": threshold,
                    "performance_issue": True,
                    "correlation_id": correlation_id,
                },
            )

    @staticmethod
    def log_external_service_error(
        service: str,
        operation: str,
        error: str,
        status_code: int | None = None,
        correlation_id: str | None = None,
    ):
        """Log external service errors."""
        logger.error(
            f"External service error - {service} {operation}: {error}",
            extra={
                "service": service,
                "operation": operation,
                "external_service_error": True,
                "status_code": status_code,
                "correlation_id": correlation_id,
            },
        )
