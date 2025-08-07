"""
User and OAuth Account models for FastAPI-Users integration.
"""

from datetime import datetime

from fastapi_users.db import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Forward references for type hints
if False:  # TYPE_CHECKING
    from .attendee import Attendee
    from .event import Event
    from .password_reset import PasswordResetToken
    from .qr_login import QRLogin


class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    Extended User model with additional fields for the speed dating app.
    Inherits from FastAPI-Users base class for OAuth2 integration.
    """

    __tablename__ = "user"

    # Additional user fields
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    display_name: Mapped[str | None] = mapped_column(String(200))

    # Role management
    is_organizer: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Profile information
    profile_picture_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str | None] = mapped_column(String(500))

    # Contact information for match purposes
    contact_phone: Mapped[str | None] = mapped_column(
        String(25)
    )  # Increased for formatted UK numbers
    fetlife_username: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        "OAuthAccount", back_populates="user", cascade="all, delete-orphan"
    )
    attendee_profiles: Mapped[list["Attendee"]] = relationship(
        "Attendee", back_populates="user", cascade="all, delete-orphan"
    )
    organized_events: Mapped[list["Event"]] = relationship(
        "Event", back_populates="organizer", cascade="all, delete-orphan"
    )
    qr_logins: Mapped[list["QRLogin"]] = relationship(
        "QRLogin", back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, display_name={self.display_name})>"

    @property
    def full_name(self) -> str:
        """Return the user's full name or display name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.display_name:
            return self.display_name
        else:
            return self.email.split("@")[0]  # Use email prefix as fallback

    def has_contact_info(self) -> bool:
        """Check if user has at least one contact method for event participation."""
        return bool(self.email or self.contact_phone or self.fetlife_username)


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    """
    OAuth Account model for storing OAuth provider information.
    Supports multiple OAuth providers per user.
    """

    __tablename__ = "oauth_account"

    # Additional OAuth fields
    account_email: Mapped[str | None] = mapped_column(String(320))
    account_name: Mapped[str | None] = mapped_column(String(200))
    account_picture: Mapped[str | None] = mapped_column(String(500))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")

    def __repr__(self) -> str:
        return f"<OAuthAccount(id={self.id}, oauth_name={self.oauth_name}, account_id={self.account_id})>"
