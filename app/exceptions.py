"""
Custom exception classes for the Speed Dating application.

Provides centralized error handling with consistent error messages,
status codes, and logging integration.
"""

from typing import Any

from fastapi import HTTPException, status


class SpeedDatingException(Exception):
    """Base exception class for all Speed Dating application errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(message)

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return HTTPException(
            status_code=self.status_code,
            detail={
                "error": self.error_code,
                "message": self.message,
                "details": self.details,
            },
        )


class ValidationError(SpeedDatingException):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        details: dict[str, Any] | None = None,
    ):
        validation_details = details or {}
        if field:
            validation_details["field"] = field
        if value is not None:
            validation_details["invalid_value"] = str(value)

        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=validation_details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class NotFoundError(SpeedDatingException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str | None = None,
        message: str | None = None,
    ):
        if message is None:
            if resource_id:
                message = f"{resource_type} with ID '{resource_id}' not found"
            else:
                message = f"{resource_type} not found"

        details = {"resource_type": resource_type}
        if resource_id:
            details["resource_id"] = resource_id

        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            details=details,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class AuthenticationError(SpeedDatingException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_REQUIRED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(SpeedDatingException):
    """Raised when user lacks required permissions."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        required_permission: str | None = None,
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission

        super().__init__(
            message=message,
            error_code="INSUFFICIENT_PERMISSIONS",
            details=details,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class BusinessLogicError(SpeedDatingException):
    """Raised when business logic constraints are violated."""

    def __init__(
        self,
        message: str,
        rule: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        business_details = details or {}
        if rule:
            business_details["violated_rule"] = rule

        super().__init__(
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            details=business_details,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class DatabaseError(SpeedDatingException):
    """Raised when database operations fail."""

    def __init__(
        self,
        message: str = "Database operation failed",
        operation: str | None = None,
        table: str | None = None,
    ):
        details = {}
        if operation:
            details["operation"] = operation
        if table:
            details["table"] = table

        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ConfigurationError(SpeedDatingException):
    """Raised when application configuration is invalid."""

    def __init__(
        self, message: str, setting: str | None = None, value: str | None = None
    ):
        details = {}
        if setting:
            details["setting"] = setting
        if value:
            details["invalid_value"] = value

        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ExternalServiceError(SpeedDatingException):
    """Raised when external service integration fails."""

    def __init__(
        self,
        message: str,
        service: str,
        operation: str | None = None,
        status_code: int = status.HTTP_502_BAD_GATEWAY,
    ):
        details = {"service": service}
        if operation:
            details["operation"] = operation

        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            details=details,
            status_code=status_code,
        )


class QRCodeError(SpeedDatingException):
    """Raised when QR code operations fail."""

    def __init__(
        self, message: str, token: str | None = None, operation: str | None = None
    ):
        details = {}
        if token:
            details["token"] = token[:10] + "..." if len(token) > 10 else token
        if operation:
            details["operation"] = operation

        super().__init__(
            message=message,
            error_code="QR_CODE_ERROR",
            details=details,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class EventError(SpeedDatingException):
    """Raised when event-specific operations fail."""

    def __init__(
        self, message: str, event_id: str | None = None, event_status: str | None = None
    ):
        details = {}
        if event_id:
            details["event_id"] = event_id
        if event_status:
            details["event_status"] = event_status

        super().__init__(
            message=message,
            error_code="EVENT_ERROR",
            details=details,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class MatchingError(SpeedDatingException):
    """Raised when matching algorithm encounters errors."""

    def __init__(
        self,
        message: str,
        algorithm: str | None = None,
        participant_count: int | None = None,
    ):
        details = {}
        if algorithm:
            details["algorithm"] = algorithm
        if participant_count is not None:
            details["participant_count"] = participant_count

        super().__init__(
            message=message,
            error_code="MATCHING_ERROR",
            details=details,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class RateLimitError(SpeedDatingException):
    """Raised when rate limits are exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: int | None = None,
        reset_time: int | None = None,
    ):
        details = {}
        if limit:
            details["limit"] = limit
        if reset_time:
            details["reset_time"] = reset_time

        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class WebSocketError(SpeedDatingException):
    """Raised when WebSocket operations fail."""

    def __init__(
        self,
        message: str,
        connection_id: str | None = None,
        operation: str | None = None,
    ):
        details = {}
        if connection_id:
            details["connection_id"] = connection_id
        if operation:
            details["operation"] = operation

        super().__init__(
            message=message,
            error_code="WEBSOCKET_ERROR",
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Convenience functions for common error scenarios
def validation_error(message: str, field: str | None = None, value: Any | None = None):
    """Create and raise a validation error."""
    raise ValidationError(message=message, field=field, value=value)


def not_found(resource_type: str, resource_id: str | None = None):
    """Create and raise a not found error."""
    raise NotFoundError(resource_type=resource_type, resource_id=resource_id)


def unauthorized(message: str = "Authentication required"):
    """Create and raise an authentication error."""
    raise AuthenticationError(message=message)


def forbidden(
    message: str = "Insufficient permissions", required_permission: str | None = None
):
    """Create and raise an authorization error."""
    raise AuthorizationError(message=message, required_permission=required_permission)


def business_error(message: str, rule: str | None = None):
    """Create and raise a business logic error."""
    raise BusinessLogicError(message=message, rule=rule)


def database_error(
    message: str = "Database operation failed",
    operation: str | None = None,
    table: str | None = None,
):
    """Create and raise a database error."""
    raise DatabaseError(message=message, operation=operation, table=table)
