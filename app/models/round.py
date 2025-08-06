"""
Round model for speed dating event rounds.
"""

import uuid
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Forward references for type hints
if False:  # TYPE_CHECKING
    from .event import Event
    from .match import Match


class RoundStatus(str, Enum):
    """Round status enumeration."""

    PENDING = "pending"
    ACTIVE = "active"
    BREAK = "break"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Round(Base):
    """
    Round model representing a single round of speed dating.
    Contains timing, status, and relationship to matches.
    """

    __tablename__ = "round"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Round identification
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))

    # Round timing
    duration_minutes: Mapped[int] = mapped_column(Integer, default=5)
    break_after_minutes: Mapped[int] = mapped_column(Integer, default=2)

    # Scheduled timing
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Actual timing
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Round status
    status: Mapped[RoundStatus] = mapped_column(default=RoundStatus.PENDING)
    is_break_active: Mapped[bool] = mapped_column(Boolean, default=False)

    # Round information
    announcements: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(String(500))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Foreign keys
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="rounds")
    matches: Mapped[list["Match"]] = relationship(
        "Match", back_populates="round", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Round(id={self.id}, number={self.round_number}, status={self.status})>"
        )

    @property
    def total_matches(self) -> int:
        """Get the total number of matches in this round."""
        return len(self.matches)

    @property
    def completed_matches(self) -> int:
        """Get the number of completed matches (both attendees responded)."""
        return len([m for m in self.matches if m.both_responded])

    @property
    def completion_percentage(self) -> float:
        """Get the completion percentage of matches in this round."""
        if self.total_matches == 0:
            return 0.0
        return (self.completed_matches / self.total_matches) * 100

    def start_round(self) -> None:
        """Start the round."""
        if self.status != RoundStatus.PENDING:
            raise ValueError(f"Cannot start round with status {self.status}")

        self.status = RoundStatus.ACTIVE
        self.actual_start = datetime.utcnow()
        self.is_break_active = False

    def start_break(self) -> None:
        """Start the break period for this round."""
        if self.status != RoundStatus.ACTIVE:
            raise ValueError(f"Cannot start break from status {self.status}")

        self.status = RoundStatus.BREAK
        self.is_break_active = True

    def end_round(self) -> None:
        """End the round."""
        if self.status not in [RoundStatus.ACTIVE, RoundStatus.BREAK]:
            raise ValueError(f"Cannot end round with status {self.status}")

        self.status = RoundStatus.COMPLETED
        self.actual_end = datetime.utcnow()
        self.is_break_active = False

    def cancel_round(self, reason: str | None = None) -> None:
        """Cancel the round."""
        self.status = RoundStatus.CANCELLED
        if reason:
            self.notes = f"Cancelled: {reason}"

    def get_duration_info(self) -> dict:
        """Get timing information for this round."""
        now = datetime.utcnow()

        info = {
            "round_id": str(self.id),
            "status": self.status.value,
            "duration_minutes": self.duration_minutes,
            "break_minutes": self.break_after_minutes,
            "scheduled_start": self.scheduled_start.isoformat()
            if self.scheduled_start
            else None,
            "scheduled_end": self.scheduled_end.isoformat()
            if self.scheduled_end
            else None,
            "actual_start": self.actual_start.isoformat()
            if self.actual_start
            else None,
            "actual_end": self.actual_end.isoformat() if self.actual_end else None,
            "is_break_active": self.is_break_active,
        }

        if self.status == RoundStatus.PENDING:
            info["time_until_start"] = None
            if self.scheduled_start:
                delta = (self.scheduled_start - now).total_seconds()
                info["time_until_start"] = max(0, int(delta))

        elif self.status == RoundStatus.ACTIVE and self.actual_start:
            elapsed = (now - self.actual_start).total_seconds()
            remaining = max(0, (self.duration_minutes * 60) - elapsed)
            info["time_remaining"] = int(remaining)
            info["elapsed_time"] = int(elapsed)

        elif self.status == RoundStatus.BREAK and self.actual_start:
            # Calculate break time
            round_end = self.actual_start + timedelta(minutes=self.duration_minutes)
            break_elapsed = (now - round_end).total_seconds()
            break_remaining = max(0, (self.break_after_minutes * 60) - break_elapsed)
            info["break_time_remaining"] = int(break_remaining)
            info["break_elapsed"] = int(break_elapsed)

        return info
