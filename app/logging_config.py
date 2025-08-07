"""
Logging configuration for the Speed Dating application.

Provides structured logging with different levels, formatters, and handlers
for development and production environments.
"""

import logging
import logging.config
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings


class CorrelationFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record):
        # Try to get correlation ID from context
        correlation_id = getattr(record, "correlation_id", None)
        if not correlation_id:
            # Try to get from request context if available
            try:
                import contextvars

                correlation_var = contextvars.ContextVar(
                    "correlation_id", default="unknown"
                )
                correlation_id = correlation_var.get()
            except (ImportError, LookupError):
                correlation_id = "unknown"

        record.correlation_id = correlation_id
        return True


class CustomFormatter(logging.Formatter):
    """Custom formatter with correlation ID and structured output."""

    def __init__(self, include_correlation: bool = True):
        self.include_correlation = include_correlation
        super().__init__()

    def format(self, record):
        # Add timestamp
        record.timestamp = datetime.now(UTC).isoformat()

        # Base format
        if self.include_correlation:
            fmt = "[{timestamp}] [{levelname}] [{correlation_id}] {name}: {message}"
        else:
            fmt = "[{timestamp}] [{levelname}] {name}: {message}"

        # Add extra context if available
        extra_fields = []
        for field in [
            "user_id",
            "operation",
            "error_code",
            "performance_issue",
            "security_event",
        ]:
            if hasattr(record, field):
                extra_fields.append(f"{field}={getattr(record, field)}")

        if extra_fields:
            fmt += f" | {' | '.join(extra_fields)}"

        formatter = logging.Formatter(fmt, style="{")
        return formatter.format(record)


class SecurityFilter(logging.Filter):
    """Filter to add security event markers."""

    def filter(self, record):
        # Mark security-related log entries
        security_keywords = [
            "authentication",
            "authorization",
            "login",
            "logout",
            "password",
            "token",
            "permission",
            "access",
            "security",
            "attack",
            "breach",
        ]

        message = record.getMessage().lower()
        if any(keyword in message for keyword in security_keywords):
            record.security_event = True

        return True


def setup_logging():
    """Configure logging for the application."""

    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Determine log level from environment
    log_level = getattr(settings, "LOG_LEVEL", "INFO").upper()
    if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        log_level = "INFO"

    # Development vs Production configuration
    is_development = getattr(settings, "ENVIRONMENT", "development") == "development"

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "correlation": {
                "()": CorrelationFilter,
            },
            "security": {
                "()": SecurityFilter,
            },
        },
        "formatters": {
            "detailed": {
                "()": CustomFormatter,
                "include_correlation": True,
            },
            "simple": {
                "format": "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "correlation_id": "%(correlation_id)s"}',
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "detailed" if is_development else "simple",
                "filters": ["correlation", "security"],
                "stream": sys.stdout,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filters": ["correlation", "security"],
                "filename": log_dir / "app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filters": ["correlation", "security"],
                "filename": log_dir / "error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "encoding": "utf-8",
            },
            "security_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "WARNING",
                "formatter": "detailed",
                "filters": ["security"],
                "filename": log_dir / "security.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "app": {
                "level": log_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "app.security": {
                "level": "WARNING",
                "handlers": ["console", "file", "security_file"],
                "propagate": False,
            },
            "app.middleware.error_handler": {
                "level": "WARNING",
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING" if is_development else "ERROR",
                "handlers": ["file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"] if is_development else ["file"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO" if is_development else "WARNING",
                "handlers": ["file"],
                "propagate": False,
            },
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console", "error_file"],
        },
    }

    # Apply configuration
    logging.config.dictConfig(logging_config)

    # Log startup message
    logger = logging.getLogger("app")
    logger.info(
        f"Logging configured - Level: {log_level}, Environment: {getattr(settings, 'ENVIRONMENT', 'development')}",
        extra={"operation": "startup"},
    )


def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance with proper configuration."""
    if name is None:
        name = "app"
    elif not name.startswith("app."):
        name = f"app.{name}"

    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter that adds context to log messages."""

    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})

    def process(self, msg, kwargs):
        # Add extra context to all log messages
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        # Merge adapter extra with message extra
        kwargs["extra"].update(self.extra)

        return msg, kwargs

    def with_context(self, **context):
        """Create a new adapter with additional context."""
        new_extra = self.extra.copy()
        new_extra.update(context)
        return LoggerAdapter(self.logger, new_extra)


def get_contextual_logger(name: str = None, **context) -> LoggerAdapter:
    """Get a logger with additional context."""
    logger = get_logger(name)
    return LoggerAdapter(logger, context)


# Performance monitoring decorator
def log_performance(operation: str, threshold: float = 5.0):
    """Decorator to log performance metrics for functions."""

    def decorator(func):
        import functools
        import time

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger("performance")
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                if duration > threshold:
                    logger.warning(
                        f"Performance issue in {operation}: {duration:.2f}s",
                        extra={
                            "operation": operation,
                            "duration": duration,
                            "threshold": threshold,
                            "performance_issue": True,
                        },
                    )
                else:
                    logger.debug(
                        f"Performance OK for {operation}: {duration:.2f}s",
                        extra={"operation": operation, "duration": duration},
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Error in {operation} after {duration:.2f}s: {str(e)}",
                    extra={
                        "operation": operation,
                        "duration": duration,
                        "error": str(e),
                    },
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger("performance")
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                if duration > threshold:
                    logger.warning(
                        f"Performance issue in {operation}: {duration:.2f}s",
                        extra={
                            "operation": operation,
                            "duration": duration,
                            "threshold": threshold,
                            "performance_issue": True,
                        },
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Error in {operation} after {duration:.2f}s: {str(e)}",
                    extra={
                        "operation": operation,
                        "duration": duration,
                        "error": str(e),
                    },
                )
                raise

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Initialize logging on import
if not os.getenv("PYTEST_CURRENT_TEST"):  # Don't setup logging during tests
    setup_logging()
