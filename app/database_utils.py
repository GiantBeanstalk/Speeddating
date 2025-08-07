"""
Database utilities for transaction management and error handling.

Provides utilities for managing database transactions, handling rollbacks,
and ensuring data consistency.
"""

import functools
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.exceptions import DatabaseError
from app.logging_config import get_contextual_logger
from app.middleware.error_handler import create_database_error_from_exception


class DatabaseTransactionManager:
    """Manages database transactions with automatic rollback on errors."""

    def __init__(self, session: AsyncSession, operation: str = "database_operation"):
        self.session = session
        self.operation = operation
        self.logger = get_contextual_logger("database", operation=operation)

    async def __aenter__(self):
        """Start transaction."""
        self.logger.debug(f"Starting database transaction for {self.operation}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Handle transaction completion or rollback."""
        try:
            if exc_type is None:
                # No exception, commit the transaction
                await self.session.commit()
                self.logger.debug(
                    f"Transaction committed successfully for {self.operation}"
                )
            else:
                # Exception occurred, rollback the transaction
                await self.session.rollback()
                self.logger.warning(
                    f"Transaction rolled back due to error in {self.operation}: {exc_val}",
                    extra={"error_type": exc_type.__name__ if exc_type else "Unknown"},
                )

                # Convert SQLAlchemy exceptions to custom exceptions
                if isinstance(exc_val, SQLAlchemyError):
                    db_error = create_database_error_from_exception(
                        exc_val, self.operation
                    )
                    # Replace the original exception with our custom one
                    raise db_error from exc_val

        except SQLAlchemyError as e:
            # Error during rollback/commit
            self.logger.error(
                f"Error during transaction cleanup in {self.operation}: {str(e)}"
            )
            await self.session.rollback()
            raise DatabaseError(
                message=f"Transaction cleanup failed in {self.operation}",
                operation=self.operation,
            ) from e


@asynccontextmanager
async def database_transaction(
    session: AsyncSession | None = None, operation: str = "database_operation"
) -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database transactions with automatic error handling.

    Args:
        session: Existing session to use, or None to create a new one
        operation: Name of the operation for logging

    Yields:
        AsyncSession: Database session within transaction
    """
    # Use provided session or create new one
    if session is None:
        async with get_async_session() as new_session:
            async with DatabaseTransactionManager(new_session, operation):
                yield new_session
    else:
        async with DatabaseTransactionManager(session, operation):
            yield session


def with_database_transaction(operation: str = None):
    """
    Decorator for automatic database transaction management.

    Args:
        operation: Name of the operation for logging
    """

    def decorator(func: Callable) -> Callable:
        op_name = operation or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Look for existing session in arguments
            session = None
            for arg in args:
                if isinstance(arg, AsyncSession):
                    session = arg
                    break

            # Look for session in keyword arguments
            if not session and "session" in kwargs:
                session = kwargs["session"]

            if session:
                # Use existing session
                async with DatabaseTransactionManager(session, op_name):
                    return await func(*args, **kwargs)
            else:
                # Create new session
                async with database_transaction(operation=op_name) as new_session:
                    # Inject session into kwargs if the function expects it
                    import inspect

                    sig = inspect.signature(func)
                    if "session" in sig.parameters:
                        kwargs["session"] = new_session

                    return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, just call the original function
            # (since they likely don't use async sessions)
            return func(*args, **kwargs)

        # Return appropriate wrapper
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class DatabaseOperationBuilder:
    """Builder for complex database operations with validation and error handling."""

    def __init__(self, session: AsyncSession, operation: str):
        self.session = session
        self.operation = operation
        self.logger = get_contextual_logger("database", operation=operation)
        self.pre_checks = []
        self.post_checks = []
        self.rollback_actions = []

    def add_pre_check(self, check_func: Callable, error_message: str):
        """Add a pre-operation validation check."""
        self.pre_checks.append((check_func, error_message))
        return self

    def add_post_check(self, check_func: Callable, error_message: str):
        """Add a post-operation validation check."""
        self.post_checks.append((check_func, error_message))
        return self

    def add_rollback_action(self, action_func: Callable):
        """Add an action to perform during rollback."""
        self.rollback_actions.append(action_func)
        return self

    async def execute(self, operation_func: Callable, *args, **kwargs):
        """Execute the operation with all checks and error handling."""
        try:
            # Run pre-checks
            for check_func, error_message in self.pre_checks:
                if not await check_func():
                    raise DatabaseError(message=error_message, operation=self.operation)

            # Execute the main operation
            result = await operation_func(self.session, *args, **kwargs)

            # Run post-checks
            for check_func, error_message in self.post_checks:
                if not await check_func(result):
                    raise DatabaseError(message=error_message, operation=self.operation)

            return result

        except Exception:
            # Execute rollback actions
            for action in self.rollback_actions:
                try:
                    await action()
                except Exception as rollback_error:
                    self.logger.error(f"Rollback action failed: {str(rollback_error)}")

            # Re-raise the original exception
            raise


def validate_database_constraints(
    model_class, data: dict, session: AsyncSession, exclude_id: Any | None = None
):
    """
    Validate database constraints before performing operations.

    Args:
        model_class: SQLAlchemy model class
        data: Data to validate
        session: Database session
        exclude_id: ID to exclude from uniqueness checks (for updates)
    """
    # This would implement constraint validation logic
    # For example, checking unique constraints, foreign key existence, etc.
    pass


async def safe_database_operation(
    operation_func: Callable,
    session: AsyncSession,
    operation_name: str,
    *args,
    **kwargs,
) -> Any:
    """
    Execute a database operation safely with comprehensive error handling.

    Args:
        operation_func: The database operation function to execute
        session: Database session
        operation_name: Name of the operation for logging
        *args: Arguments for the operation function
        **kwargs: Keyword arguments for the operation function

    Returns:
        Result of the operation function
    """
    logger = get_contextual_logger("database", operation=operation_name)

    try:
        logger.debug(f"Starting database operation: {operation_name}")
        result = await operation_func(session, *args, **kwargs)
        logger.debug(f"Database operation completed successfully: {operation_name}")
        return result

    except IntegrityError as e:
        logger.warning(f"Integrity constraint violation in {operation_name}: {str(e)}")
        await session.rollback()

        # Provide more specific error messages
        error_msg = "Data integrity constraint violated"
        if "UNIQUE constraint failed" in str(e):
            error_msg = "Record with this information already exists"
        elif "NOT NULL constraint failed" in str(e):
            error_msg = "Required information is missing"
        elif "FOREIGN KEY constraint failed" in str(e):
            error_msg = "Referenced record does not exist"

        raise DatabaseError(message=error_msg, operation=operation_name) from e

    except OperationalError as e:
        logger.error(f"Database operational error in {operation_name}: {str(e)}")
        await session.rollback()
        raise DatabaseError(
            message="Database connection or operational error", operation=operation_name
        ) from e

    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error in {operation_name}: {str(e)}")
        await session.rollback()
        raise DatabaseError(
            message=f"Database operation failed in {operation_name}",
            operation=operation_name,
        ) from e

    except Exception as e:
        logger.error(f"Unexpected error in {operation_name}: {str(e)}")
        await session.rollback()
        raise


# Utility functions for common database patterns


async def get_or_404(session: AsyncSession, model_class, **filters):
    """Get a record or raise 404 error."""
    from sqlalchemy import select

    from app.exceptions import not_found

    stmt = select(model_class).filter_by(**filters)
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        not_found(model_class.__name__, str(filters))

    return record


async def create_with_validation(
    session: AsyncSession, model_class, data: dict, operation: str = "create"
) -> Any:
    """Create a new record with validation."""
    async with safe_database_operation(
        lambda s, cls, d: _create_record(s, cls, d),
        session,
        f"create_{model_class.__name__.lower()}",
        model_class,
        data,
    ) as result:
        return result


async def _create_record(session: AsyncSession, model_class, data: dict):
    """Internal function to create a record."""
    record = model_class(**data)
    session.add(record)
    await session.flush()  # Get the ID without committing
    await session.refresh(record)
    return record


async def update_with_validation(
    session: AsyncSession, record: Any, data: dict, operation: str = "update"
) -> Any:
    """Update a record with validation."""
    async with safe_database_operation(
        lambda s, r, d: _update_record(s, r, d),
        session,
        f"update_{record.__class__.__name__.lower()}",
        record,
        data,
    ) as result:
        return result


async def _update_record(session: AsyncSession, record: Any, data: dict):
    """Internal function to update a record."""
    for key, value in data.items():
        if hasattr(record, key):
            setattr(record, key, value)

    await session.flush()
    await session.refresh(record)
    return record
