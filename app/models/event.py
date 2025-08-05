"""
Event model for speed dating events.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Forward references for type hints
if False:  # TYPE_CHECKING
    from .user import User
    from .attendee import Attendee
    from .round import Round
    from .match import Match


class EventStatus(str, Enum):
    """Event status enumeration."""
    DRAFT = "draft"
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_CLOSED = "registration_closed"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Event(Base):
    """
    Event model representing a speed dating event.
    Contains event details, configuration, and relationships to attendees and rounds.
    """
    __tablename__ = "event"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # Basic event information
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Event timing
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    registration_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Event configuration
    round_duration_minutes: Mapped[int] = mapped_column(Integer, default=5)
    break_duration_minutes: Mapped[int] = mapped_column(Integer, default=2)
    max_attendees: Mapped[int] = mapped_column(Integer, default=100)
    min_attendees: Mapped[int] = mapped_column(Integer, default=6)
    
    # Pricing information
    ticket_price: Mapped[Optional[int]] = mapped_column(Integer)  # Price in cents
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    
    # Event status and visibility
    status: Mapped[EventStatus] = mapped_column(default=EventStatus.DRAFT)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Event countdown fields
    countdown_active: Mapped[bool] = mapped_column(Boolean, default=False)
    countdown_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    countdown_target_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    countdown_message: Mapped[Optional[str]] = mapped_column(String(500))
    
    # QR Code security
    qr_secret_key: Mapped[Optional[str]] = mapped_column(String(100))
    
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
    organizer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Relationships
    organizer: Mapped["User"] = relationship("User", back_populates="organized_events")
    attendees: Mapped[list["Attendee"]] = relationship(
        "Attendee",
        back_populates="event",
        cascade="all, delete-orphan"
    )
    rounds: Mapped[list["Round"]] = relationship(
        "Round",
        back_populates="event",
        cascade="all, delete-orphan"
    )
    matches: Mapped[list["Match"]] = relationship(
        "Match",
        back_populates="event",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, name={self.name}, status={self.status})>"

    @property
    def attendee_count(self) -> int:
        """Get the number of confirmed attendees."""
        return len([a for a in self.attendees if a.registration_confirmed])

    @property
    def is_full(self) -> bool:
        """Check if the event is at maximum capacity."""
        return self.attendee_count >= self.max_attendees

    @property
    def is_registration_open(self) -> bool:
        """Check if registration is currently open."""
        if self.status != EventStatus.REGISTRATION_OPEN:
            return False
        
        if self.registration_deadline:
            return datetime.utcnow() < self.registration_deadline
        
        return not self.is_full

    def generate_qr_secret(self) -> str:
        """Generate a secret key for QR code security."""
        import secrets
        self.qr_secret_key = secrets.token_urlsafe(32)
        return self.qr_secret_key

    def can_register(self) -> tuple[bool, str]:
        """
        Check if new attendees can register for this event.
        
        Returns:
            Tuple of (can_register, reason)
        """
        if self.status != EventStatus.REGISTRATION_OPEN:
            return False, f"Registration is {self.status.value.replace('_', ' ')}"
        
        if self.is_full:
            return False, "Event is at maximum capacity"
        
        if self.registration_deadline and datetime.utcnow() > self.registration_deadline:
            return False, "Registration deadline has passed"
        
        return True, "Registration is open"

    def start_countdown(self, duration_minutes: int, message: Optional[str] = None) -> None:
        """
        Start an event countdown timer.
        
        Args:
            duration_minutes: Duration of countdown in minutes
            message: Optional custom message to display during countdown
        """
        if duration_minutes <= 0 or duration_minutes > 60:
            raise ValueError("Countdown duration must be between 1 and 60 minutes")
        
        now = datetime.utcnow()
        self.countdown_active = True
        self.countdown_start_time = now
        self.countdown_target_time = now + timedelta(minutes=duration_minutes)
        self.countdown_message = message or f"Event starts in {duration_minutes} minutes!"

    def stop_countdown(self) -> None:
        """Stop the active countdown."""
        self.countdown_active = False
        self.countdown_start_time = None
        self.countdown_target_time = None
        self.countdown_message = None

    def extend_countdown(self, additional_minutes: int) -> None:
        """
        Extend the current countdown by additional minutes.
        
        Args:
            additional_minutes: Additional minutes to add to countdown
        """
        if not self.countdown_active or not self.countdown_target_time:
            raise ValueError("No active countdown to extend")
        
        if additional_minutes <= 0 or additional_minutes > 30:
            raise ValueError("Additional minutes must be between 1 and 30")
        
        self.countdown_target_time += timedelta(minutes=additional_minutes)

    def get_countdown_status(self) -> dict:
        """
        Get current countdown status information.
        
        Returns:
            Dictionary with countdown status details
        """
        if not self.countdown_active or not self.countdown_start_time or not self.countdown_target_time:
            return {
                "active": False,
                "time_remaining": 0,
                "total_duration": 0,
                "percentage_complete": 0,
                "message": None,
                "target_time": None
            }
        
        now = datetime.utcnow()
        
        # If countdown has passed, mark as inactive
        if now >= self.countdown_target_time:
            return {
                "active": False,
                "time_remaining": 0,
                "total_duration": int((self.countdown_target_time - self.countdown_start_time).total_seconds()),
                "percentage_complete": 100,
                "message": self.countdown_message,
                "target_time": self.countdown_target_time.isoformat(),
                "completed": True
            }
        
        total_seconds = int((self.countdown_target_time - self.countdown_start_time).total_seconds())
        elapsed_seconds = int((now - self.countdown_start_time).total_seconds())
        remaining_seconds = int((self.countdown_target_time - now).total_seconds())
        percentage = (elapsed_seconds / total_seconds * 100) if total_seconds > 0 else 0
        
        return {
            "active": True,
            "time_remaining": remaining_seconds,
            "total_duration": total_seconds,
            "percentage_complete": min(100, max(0, percentage)),
            "message": self.countdown_message,
            "target_time": self.countdown_target_time.isoformat(),
            "completed": False
        }

    def can_start(self) -> tuple[bool, str]:
        """
        Check if the event can be started.
        
        Returns:
            Tuple of (can_start, reason)
        """
        if self.status not in [EventStatus.REGISTRATION_CLOSED, EventStatus.REGISTRATION_OPEN]:
            return False, f"Cannot start event with status {self.status.value}"
        
        if self.attendee_count < self.min_attendees:
            return False, f"Need at least {self.min_attendees} attendees to start (currently {self.attendee_count})"
        
        # Check if attendees are balanced
        from .attendee import AttendeeCategory
        categories = {}
        for attendee in self.attendees:
            if attendee.registration_confirmed:
                categories[attendee.category] = categories.get(attendee.category, 0) + 1
        
        # Basic balance check - ensure we have people to match
        if len(categories) < 2:
            return False, "Need attendees from multiple categories to create matches"
        
        return True, "Event can be started"