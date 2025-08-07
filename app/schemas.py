"""
User schemas for FastAPI-Users integration.

Provides Pydantic models for user creation, reading, and updating.
"""

import uuid

from fastapi_users import schemas
from pydantic import EmailStr


class UserRead(schemas.BaseUser[uuid.UUID]):
    """User read schema - data returned when reading user info."""

    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    phone: str | None = None
    fetlife_username: str | None = None


class UserCreate(schemas.BaseUserCreate):
    """User creation schema - data required to create a new user."""

    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    phone: str | None = None
    fetlife_username: str | None = None
    is_active: bool | None = True
    is_superuser: bool | None = False
    is_verified: bool | None = False


class UserUpdate(schemas.BaseUserUpdate):
    """User update schema - data that can be updated for existing users."""

    password: str | None = None
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    phone: str | None = None
    fetlife_username: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    is_verified: bool | None = None
