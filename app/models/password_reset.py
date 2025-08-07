"""
Password Reset Token model for local user password resets.

Provides secure token-based password reset functionality for users
who registered with email/password (not OAuth).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Forward reference for type hints
if False:  # TYPE_CHECKING
    from .user import User


class PasswordResetToken(Base):
    """
    Password reset token for secure password reset flow.
    
    Stores temporary tokens that allow users to reset their passwords
    through email-based verification.
    """
    
    __tablename__ = "password_reset_token"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # User reference
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), index=True)
    
    # Token data
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(UTC)
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="password_reset_tokens")
    
    def __repr__(self) -> str:
        return (
            f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, "
            f"expires_at={self.expires_at}, used={self.used})>"
        )
    
    @property
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        return datetime.now(UTC) > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if the token is valid (not used and not expired)."""
        return not self.used and not self.is_expired
    
    def mark_used(self, ip_address: str = None, user_agent: str = None) -> None:
        """Mark the token as used."""
        self.used = True
        self.used_at = datetime.now(UTC)
        if ip_address:
            self.ip_address = ip_address
        if user_agent:
            self.user_agent = user_agent[:500]  # Truncate to fit column
    
    @classmethod
    def create_token(
        cls, 
        user_id: uuid.UUID, 
        token: str, 
        expires_in_minutes: int = 60
    ) -> "PasswordResetToken":
        """
        Create a new password reset token.
        
        Args:
            user_id: ID of the user requesting reset
            token: Secure token string
            expires_in_minutes: Token expiration time in minutes
            
        Returns:
            New PasswordResetToken instance
        """
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
        
        return cls(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )