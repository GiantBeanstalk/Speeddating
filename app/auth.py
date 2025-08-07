"""
Authentication dependencies and utilities.

This module provides authentication dependencies for FastAPI endpoints.
It integrates with FastAPI-Users for OAuth2 and user management.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session
from app.models import OAuthAccount, User
from app.schemas import UserCreate, UserRead, UserUpdate

# JWT Authentication configuration
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.get("SECRET_KEY", "your-secret-key-here"),
        lifetime_seconds=3600,  # 1 hour
    )

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
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


async def get_current_user_websocket(token: str, session: AsyncSession) -> User | None:
    """Get current user from WebSocket token."""
    try:
        # This is a simplified implementation
        # In a real app, you'd validate the JWT token here
        from app.models import User
        from sqlalchemy import select
        
        # For testing, just return None (would validate token in production)
        return None
    except Exception:
        return None


# User manager for FastAPI-Users
class UserManager(BaseUserManager[User, uuid.UUID]):
    """User manager for handling user operations."""

    reset_password_token_secret = settings.get("SECRET_KEY", "your-secret-key-here")
    verification_token_secret = settings.get("SECRET_KEY", "your-secret-key-here")

    async def on_after_register(self, user: User, request=None):
        """Called after user registration."""
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(self, user: User, token: str, request=None):
        """Called after user requests password reset."""
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(self, user: User, token: str, request=None):
        """Called after user requests verification."""
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    """Get user manager dependency."""
    yield UserManager(user_db)




# Export authentication routers
auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
reset_password_router = fastapi_users.get_reset_password_router()
verify_router = fastapi_users.get_verify_router(UserRead)
users_router = fastapi_users.get_users_router(UserRead, UserUpdate)
