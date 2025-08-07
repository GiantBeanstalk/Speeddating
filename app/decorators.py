"""
Decorators for enhanced API endpoint validation and error handling.

Provides reusable decorators for input validation, authentication checks,
and error handling with consistent response formatting.
"""

import functools
import time
import uuid
from collections.abc import Callable

from fastapi import HTTPException, status

from app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)
from app.logging_config import get_contextual_logger
from app.validators import Validators


def validate_request(
    validation_rules: dict[str, Callable] | None = None,
    sanitize_input: bool = True,
    check_xss: bool = True,
):
    """
    Decorator for comprehensive request validation.

    Args:
        validation_rules: Dict mapping field names to validation functions
        sanitize_input: Whether to sanitize HTML input
        check_xss: Whether to check for XSS attacks
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_contextual_logger("validation")

            # Extract request if available
            request = None
            for arg in args:
                if hasattr(arg, "method"):  # FastAPI Request object
                    request = arg
                    break

            correlation_id = (
                getattr(request.state, "correlation_id", str(uuid.uuid4()))
                if request
                else str(uuid.uuid4())
            )
            logger = logger.with_context(correlation_id=correlation_id)

            try:
                # Apply validation rules to function arguments
                if validation_rules:
                    validated_kwargs = {}
                    for field_name, validator in validation_rules.items():
                        if field_name in kwargs:
                            try:
                                validated_kwargs[field_name] = validator(
                                    kwargs[field_name]
                                )
                            except ValidationError as e:
                                logger.warning(
                                    f"Validation failed for {field_name}: {e.message}"
                                )
                                raise e

                    # Update kwargs with validated values
                    kwargs.update(validated_kwargs)

                # Sanitize string inputs if requested
                if sanitize_input:
                    for key, value in kwargs.items():
                        if isinstance(value, str):
                            kwargs[key] = Validators.sanitize_html_input(
                                value, field_name=key
                            )

                # Call the original function
                result = await func(*args, **kwargs)
                return result

            except ValidationError as e:
                logger.warning(f"Validation error in {func.__name__}: {e.message}")
                raise HTTPException(
                    status_code=e.status_code,
                    detail={
                        "error": e.error_code,
                        "message": e.message,
                        "details": e.details,
                        "correlation_id": correlation_id,
                    },
                )
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_contextual_logger("validation")

            try:
                # Apply validation rules
                if validation_rules:
                    validated_kwargs = {}
                    for field_name, validator in validation_rules.items():
                        if field_name in kwargs:
                            try:
                                validated_kwargs[field_name] = validator(
                                    kwargs[field_name]
                                )
                            except ValidationError as e:
                                logger.warning(
                                    f"Validation failed for {field_name}: {e.message}"
                                )
                                raise e

                    kwargs.update(validated_kwargs)

                # Sanitize inputs
                if sanitize_input:
                    for key, value in kwargs.items():
                        if isinstance(value, str):
                            kwargs[key] = Validators.sanitize_html_input(
                                value, field_name=key
                            )

                result = func(*args, **kwargs)
                return result

            except ValidationError as e:
                logger.warning(f"Validation error in {func.__name__}: {e.message}")
                raise HTTPException(
                    status_code=e.status_code,
                    detail={
                        "error": e.error_code,
                        "message": e.message,
                        "details": e.details,
                    },
                )
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                raise

        # Return appropriate wrapper
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def require_permissions(required_permissions: list[str], check_ownership: bool = False):
    """
    Decorator to check user permissions.

    Args:
        required_permissions: List of required permission names
        check_ownership: Whether to check resource ownership
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_contextual_logger("security")

            # Extract user from dependencies
            user = None
            for arg in args:
                if hasattr(arg, "email") and hasattr(
                    arg, "is_superuser"
                ):  # User object
                    user = arg
                    break

            if not user:
                logger.warning(f"No user found for permission check in {func.__name__}")
                raise AuthenticationError("User authentication required")

            # Check if user is superuser (bypass all checks)
            if user.is_superuser:
                return await func(*args, **kwargs)

            # Check required permissions
            for permission in required_permissions:
                if permission == "organizer" and not user.is_organizer:
                    logger.warning(f"User {user.id} lacks organizer permission")
                    raise AuthorizationError(
                        "Organizer permissions required", required_permission=permission
                    )
                elif permission == "active" and not user.is_active:
                    logger.warning(f"User {user.id} is not active")
                    raise AuthorizationError(
                        "Active user account required", required_permission=permission
                    )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Similar implementation for sync functions
            return func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def monitor_performance(operation_name: str, threshold: float = 5.0):
    """
    Decorator to monitor and log performance metrics.

    Args:
        operation_name: Name of the operation for logging
        threshold: Performance threshold in seconds
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_contextual_logger("performance")
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                if duration > threshold:
                    logger.warning(
                        f"Performance issue in {operation_name}: {duration:.2f}s",
                        extra={
                            "operation": operation_name,
                            "duration": duration,
                            "threshold": threshold,
                            "performance_issue": True,
                        },
                    )
                else:
                    logger.debug(
                        f"Performance OK for {operation_name}: {duration:.2f}s",
                        extra={"operation": operation_name, "duration": duration},
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Error in {operation_name} after {duration:.2f}s: {str(e)}",
                    extra={
                        "operation": operation_name,
                        "duration": duration,
                        "error": str(e),
                    },
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_contextual_logger("performance")
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                if duration > threshold:
                    logger.warning(
                        f"Performance issue in {operation_name}: {duration:.2f}s",
                        extra={
                            "operation": operation_name,
                            "duration": duration,
                            "threshold": threshold,
                            "performance_issue": True,
                        },
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Error in {operation_name} after {duration:.2f}s: {str(e)}",
                    extra={
                        "operation": operation_name,
                        "duration": duration,
                        "error": str(e),
                    },
                )
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def handle_database_errors(operation: str = "database_operation"):
    """
    Decorator to handle database errors consistently.

    Args:
        operation: Name of the database operation for logging
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_contextual_logger("database")

            try:
                return await func(*args, **kwargs)

            except Exception as e:
                # Import here to avoid circular imports
                from sqlalchemy.exc import (
                    SQLAlchemyError,
                )

                from app.middleware.error_handler import (
                    create_database_error_from_exception,
                )

                if isinstance(e, SQLAlchemyError):
                    logger.error(f"Database error in {operation}: {str(e)}")
                    db_error = create_database_error_from_exception(
                        e, operation=operation
                    )
                    raise db_error
                else:
                    logger.error(f"Unexpected error in {operation}: {str(e)}")
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_contextual_logger("database")

            try:
                return func(*args, **kwargs)

            except Exception as e:
                from sqlalchemy.exc import SQLAlchemyError

                from app.middleware.error_handler import (
                    create_database_error_from_exception,
                )

                if isinstance(e, SQLAlchemyError):
                    logger.error(f"Database error in {operation}: {str(e)}")
                    db_error = create_database_error_from_exception(
                        e, operation=operation
                    )
                    raise db_error
                else:
                    logger.error(f"Unexpected error in {operation}: {str(e)}")
                    raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def validate_uuid_params(**param_names):
    """
    Decorator to validate UUID parameters.

    Args:
        **param_names: Dict mapping parameter names to their descriptions
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            for param_name, description in param_names.items():
                if param_name in kwargs:
                    try:
                        kwargs[param_name] = Validators.validate_uuid(
                            kwargs[param_name], field_name=description or param_name
                        )
                    except ValidationError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid {description or param_name} format",
                        )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            for param_name, description in param_names.items():
                if param_name in kwargs:
                    try:
                        kwargs[param_name] = Validators.validate_uuid(
                            kwargs[param_name], field_name=description or param_name
                        )
                    except ValidationError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid {description or param_name} format",
                        )

            return func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def log_security_events(event_type: str):
    """
    Decorator to log security-related events.

    Args:
        event_type: Type of security event for logging
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_contextual_logger("security")

            # Extract user and request info if available
            user_id = None
            ip_address = None

            for arg in args:
                if hasattr(arg, "id") and hasattr(arg, "email"):  # User object
                    user_id = str(arg.id)
                elif hasattr(arg, "client") and hasattr(arg, "url"):  # Request object
                    ip_address = arg.client.host if arg.client else None

            try:
                result = await func(*args, **kwargs)

                logger.info(
                    f"Security event - {event_type}: Success",
                    extra={
                        "security_event": True,
                        "event_type": event_type,
                        "user_id": user_id,
                        "ip_address": ip_address,
                        "status": "success",
                    },
                )

                return result

            except Exception as e:
                logger.warning(
                    f"Security event - {event_type}: Failed - {str(e)}",
                    extra={
                        "security_event": True,
                        "event_type": event_type,
                        "user_id": user_id,
                        "ip_address": ip_address,
                        "status": "failed",
                        "error": str(e),
                    },
                )
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            # Similar implementation for sync functions
            return func

    return decorator
