"""
QR Login model for secure QR code authentication.
"""
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Forward references for type hints
if False:  # TYPE_CHECKING
    from .user import User
    from .event import Event
    from .attendee import Attendee


class QRLogin(Base):
    """
    QR Login model for secure QR code-based authentication.
    Used for both event login and profile viewing.
    """
    __tablename__ = "qr_login"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # Token information
    token: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Token type and purpose
    token_type: Mapped[str] = mapped_column(String(20), default="event_login")  # "event_login" or "profile_view"
    
    # Expiration and usage
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, default=10)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Status flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[Optional[str]] = mapped_column(String(200))
    
    # QR code configuration
    qr_code_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Usage tracking
    first_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_used_ip: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6 compatible
    last_user_agent: Mapped[Optional[str]] = mapped_column(Text)
    
    # Usage history (JSON string of usage events)
    usage_history: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"),
        nullable=False
    )
    attendee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("attendee.id", ondelete="CASCADE")
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="qr_logins")
    event: Mapped["Event"] = relationship("Event")
    attendee: Mapped[Optional["Attendee"]] = relationship("Attendee")

    def __repr__(self) -> str:
        return f"<QRLogin(id={self.id}, user_id={self.user_id}, type={self.token_type})>"

    @classmethod
    def create_for_attendee(
        cls,
        attendee_id: uuid.UUID,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        expire_hours: int = 24,
        token_type: str = "event_login"
    ) -> "QRLogin":
        """Create a new QR login token for an attendee."""
        qr_login = cls(
            user_id=user_id,
            event_id=event_id,
            attendee_id=attendee_id,
            token_type=token_type,
            expires_at=datetime.utcnow() + timedelta(hours=expire_hours)
        )
        
        qr_login.generate_token()
        qr_login.hash_token()
        
        return qr_login

    def generate_token(self) -> str:
        """Generate a new random token."""
        self.token = secrets.token_urlsafe(32)
        return self.token

    def hash_token(self) -> str:
        """Hash the token for secure storage."""
        if not self.token:
            raise ValueError("No token to hash")
        
        self.token_hash = hashlib.sha256(self.token.encode()).hexdigest()
        return self.token_hash

    @property
    def is_valid(self) -> bool:
        """Check if the token is currently valid."""
        now = datetime.utcnow()
        
        return (
            self.is_active and
            not self.is_revoked and
            self.expires_at > now and
            self.usage_count < self.max_uses
        )

    @property
    def time_until_expiry(self) -> Optional[int]:
        """Get seconds until token expires."""
        if not self.expires_at:
            return None
        
        delta = self.expires_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))

    def use_token(
        self, 
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Use the token (increment usage count and update tracking).
        
        Returns:
            True if token was used successfully, False if invalid
        """
        if not self.is_valid:
            return False
        
        now = datetime.utcnow()
        
        # Update usage tracking
        if self.usage_count == 0:
            self.first_used_at = now
        
        self.usage_count += 1
        self.last_used_at = now
        
        if ip_address:
            self.last_used_ip = ip_address
        
        if user_agent:
            self.last_user_agent = user_agent
        
        # Add to usage history
        self._add_usage_event({
            "timestamp": now.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent[:200] if user_agent else None  # Truncate long user agents
        })
        
        return True

    def revoke_token(self, reason: str = "Manually revoked") -> None:
        """Revoke the token."""
        self.is_revoked = True
        self.is_active = False
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason

    def extend_expiry(self, additional_hours: int = 24) -> None:
        """Extend the token expiry time."""
        if self.expires_at:
            self.expires_at += timedelta(hours=additional_hours)
        else:
            self.expires_at = datetime.utcnow() + timedelta(hours=additional_hours)

    def _add_usage_event(self, event_data: Dict[str, Any]) -> None:
        """Add a usage event to the history."""
        import json
        
        if not self.usage_history:
            history = []
        else:
            try:
                history = json.loads(self.usage_history)
            except json.JSONDecodeError:
                history = []
        
        history.append(event_data)
        
        # Keep only last 50 events to avoid bloating
        if len(history) > 50:
            history = history[-50:]
        
        self.usage_history = json.dumps(history)

    def get_usage_events(self) -> list:
        """Get the usage history as a list of events."""
        if not self.usage_history:
            return []
        
        try:
            import json
            return json.loads(self.usage_history)
        except json.JSONDecodeError:
            return []

    def get_token_info(self) -> Dict[str, Any]:
        """Get comprehensive token information."""
        return {
            "id": str(self.id),
            "token_type": self.token_type,
            "is_valid": self.is_valid,
            "is_active": self.is_active,
            "is_revoked": self.is_revoked,
            "expires_at": self.expires_at.isoformat(),
            "time_until_expiry": self.time_until_expiry,
            "usage_count": self.usage_count,
            "max_uses": self.max_uses,
            "remaining_uses": max(0, self.max_uses - self.usage_count),
            "first_used_at": self.first_used_at.isoformat() if self.first_used_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat(),
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoked_reason": self.revoked_reason
        }