"""
Authentication dependencies and utilities.

This module provides authentication dependencies for FastAPI endpoints.
It integrates with FastAPI-Users for OAuth2 and user management.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTAuthentication,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session
from app.models import OAuthAccount, User

# JWT Authentication configuration
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
jwt_authentication = JWTAuthentication(
    secret=settings.get("SECRET_KEY", "your-secret-key-here"),
    lifetime_seconds=3600,  # 1 hour
    tokenUrl="auth/jwt/login",
)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=jwt_authentication.get_strategy,
)


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    """Get user database dependency."""
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


# FastAPI Users instance
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_db,
    [auth_backend],
)

# Authentication dependencies
current_active_user = fastapi_users.current_user(active=True)
current_active_verified_user = fastapi_users.current_user(active=True, verified=True)


async def current_active_organizer(
    current_user: User = Depends(current_active_user),
) -> User:
    """Dependency to ensure current user is an active organizer."""
    if not current_user.is_organizer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organizer privileges required",
        )
    return current_user


async def current_superuser(current_user: User = Depends(current_active_user)) -> User:
    """Dependency to ensure current user is a superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user


# Optional user dependency (doesn't require authentication)
async def optional_current_user(
    session: AsyncSession = Depends(get_async_session),
) -> User | None:
    """Optional user dependency that doesn't require authentication."""
    # This would typically extract user from token if present
    # For now, return None (anonymous user)
    return None


# User manager for FastAPI-Users
class UserManager:
    """User manager for handling user operations."""

    def __init__(self, user_db: SQLAlchemyUserDatabase):
        self.user_db = user_db

    async def create_user(self, user_create, safe: bool = False, request=None):
        """Create a new user."""
        # Implementation would go here
        pass

    async def get_by_email(self, email: str):
        """Get user by email."""
        return await self.user_db.get_by_email(email)


async def get_user_manager(user_db=Depends(get_user_db)):
    """Get user manager dependency."""
    yield UserManager(user_db)


async def get_current_user_websocket(token: str, session: AsyncSession) -> User | None:
    """
    Authenticate user for WebSocket connections using JWT token.

    Args:
        token: JWT token from WebSocket query parameter
        session: Database session

    Returns:
        User object if authentication successful, None otherwise
    """
    try:
        # Use JWT authentication strategy to decode token
        strategy = jwt_authentication.get_strategy()
        user_id = await strategy.read_token(token, None)

        if user_id:
            # Get user from database
            user_db = SQLAlchemyUserDatabase(session, User, OAuthAccount)
            user = await user_db.get(user_id)

            # Check if user is active
            if user and user.is_active:
                return user

        return None
    except Exception as e:
        print(f"WebSocket authentication error: {e}")
        return None


# Export authentication routers
auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router()
reset_password_router = fastapi_users.get_reset_password_router()
verify_router = fastapi_users.get_verify_router()
users_router = fastapi_users.get_users_router()
