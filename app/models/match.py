"""
Match model for speed dating matches between attendees.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Forward references for type hints
if False:  # TYPE_CHECKING
    from .event import Event
    from .round import Round
    from .attendee import Attendee


class MatchResponse(str, Enum):
    """Match response enumeration."""
    NO_RESPONSE = "no_response"
    YES = "yes"
    NO = "no"


class Match(Base):
    """
    Match model representing a pairing between two attendees.
    Contains match details, responses, and timing information.
    """
    __tablename__ = "match"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # Match logistics
    table_number: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Match responses
    attendee1_response: Mapped[MatchResponse] = mapped_column(default=MatchResponse.NO_RESPONSE)
    attendee2_response: Mapped[MatchResponse] = mapped_column(default=MatchResponse.NO_RESPONSE)
    
    # Response timing
    attendee1_response_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    attendee2_response_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Additional response data
    attendee1_notes: Mapped[Optional[str]] = mapped_column(Text)
    attendee2_notes: Mapped[Optional[str]] = mapped_column(Text)
    attendee1_rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5 scale
    attendee2_rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5 scale
    
    # Match metadata
    organizer_notes: Mapped[Optional[str]] = mapped_column(Text)
    
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
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"),
        nullable=False
    )
    round_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("round.id", ondelete="CASCADE")
    )
    attendee1_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendee.id", ondelete="CASCADE"),
        nullable=False
    )
    attendee2_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendee.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="matches")
    round: Mapped[Optional["Round"]] = relationship("Round", back_populates="matches")
    attendee1: Mapped["Attendee"] = relationship(
        "Attendee",
        foreign_keys=[attendee1_id],
        back_populates="matches_as_attendee1"
    )
    attendee2: Mapped["Attendee"] = relationship(
        "Attendee", 
        foreign_keys=[attendee2_id],
        back_populates="matches_as_attendee2"
    )

    def __repr__(self) -> str:
        return f"<Match(id={self.id}, attendee1_id={self.attendee1_id}, attendee2_id={self.attendee2_id})>"

    @property
    def is_mutual_match(self) -> bool:
        """Check if both attendees responded 'yes'."""
        return (
            self.attendee1_response == MatchResponse.YES and
            self.attendee2_response == MatchResponse.YES
        )

    @property
    def both_responded(self) -> bool:
        """Check if both attendees have provided responses."""
        return (
            self.attendee1_response != MatchResponse.NO_RESPONSE and
            self.attendee2_response != MatchResponse.NO_RESPONSE
        )

    @property
    def either_said_no(self) -> bool:
        """Check if either attendee said no."""
        return (
            self.attendee1_response == MatchResponse.NO or
            self.attendee2_response == MatchResponse.NO
        )

    def set_attendee_response(
        self, 
        attendee_id: uuid.UUID, 
        response: MatchResponse,
        notes: Optional[str] = None,
        rating: Optional[int] = None
    ) -> bool:
        """
        Set response for a specific attendee.
        
        Args:
            attendee_id: ID of the attendee responding
            response: The response (YES/NO)
            notes: Optional notes from the attendee
            rating: Optional rating (1-5)
            
        Returns:
            True if response was set successfully, False otherwise
        """
        now = datetime.utcnow()
        
        if attendee_id == self.attendee1_id:
            self.attendee1_response = response
            self.attendee1_response_time = now
            if notes:
                self.attendee1_notes = notes
            if rating:
                self.attendee1_rating = rating
            return True
        
        elif attendee_id == self.attendee2_id:
            self.attendee2_response = response
            self.attendee2_response_time = now
            if notes:
                self.attendee2_notes = notes
            if rating:
                self.attendee2_rating = rating
            return True
        
        return False

    def get_response_for_attendee(self, attendee_id: uuid.UUID) -> Optional[MatchResponse]:
        """Get the response from a specific attendee."""
        if attendee_id == self.attendee1_id:
            return self.attendee1_response
        elif attendee_id == self.attendee2_id:
            return self.attendee2_response
        return None

    def get_other_attendee_id(self, attendee_id: uuid.UUID) -> Optional[uuid.UUID]:
        """Get the ID of the other attendee in this match."""
        if attendee_id == self.attendee1_id:
            return self.attendee2_id
        elif attendee_id == self.attendee2_id:
            return self.attendee1_id
        return None

    def get_match_summary(self) -> dict:
        """Get a summary of the match for reporting."""
        return {
            "match_id": str(self.id),
            "event_id": str(self.event_id),
            "round_id": str(self.round_id) if self.round_id else None,
            "round_number": self.round.round_number if self.round else None,
            "table_number": self.table_number,
            "attendee1": {
                "id": str(self.attendee1_id),
                "name": self.attendee1.display_name,
                "category": self.attendee1.category.value,
                "response": self.attendee1_response.value,
                "response_time": self.attendee1_response_time.isoformat() if self.attendee1_response_time else None,
                "rating": self.attendee1_rating,
                "has_notes": bool(self.attendee1_notes)
            },
            "attendee2": {
                "id": str(self.attendee2_id),
                "name": self.attendee2.display_name,
                "category": self.attendee2.category.value,
                "response": self.attendee2_response.value,
                "response_time": self.attendee2_response_time.isoformat() if self.attendee2_response_time else None,
                "rating": self.attendee2_rating,
                "has_notes": bool(self.attendee2_notes)
            },
            "is_mutual_match": self.is_mutual_match,
            "both_responded": self.both_responded,
            "created_at": self.created_at.isoformat()
        }