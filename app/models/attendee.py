"""
Attendee models for event participation and matching preferences.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Forward references for type hints
if False:  # TYPE_CHECKING
    from .event import Event
    from .match import Match
    from .user import User


class AttendeeCategory(str, Enum):
    """Attendee categories for matching."""

    TOP_MALE = "top_male"
    TOP_FEMALE = "top_female"
    BOTTOM_MALE = "bottom_male"
    BOTTOM_FEMALE = "bottom_female"


# Association table for many-to-many relationship between attendees and their preferences
attendee_preferences = Table(
    "attendee_preferences",
    Base.metadata,
    Column(
        "attendee_id", ForeignKey("attendee.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("preferred_category", String(20), primary_key=True),
)


class Attendee(Base):
    """
    Attendee model representing a participant in a speed dating event.
    Links users to specific events with category and preference information.
    """

    __tablename__ = "attendee"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Personal information
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer)

    # Bio fields - public bio is filtered and visible to all, private bio is for internal use
    public_bio: Mapped[str | None] = mapped_column(
        Text
    )  # Filtered bio visible to all attendees
    private_bio: Mapped[str | None] = mapped_column(
        Text
    )  # Internal notes, only visible to organizers

    # Attendee category and preferences
    category: Mapped[AttendeeCategory] = mapped_column(nullable=False)

    # Event participation details
    checked_in: Mapped[bool] = mapped_column(Boolean, default=False)
    check_in_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    table_number: Mapped[int | None] = mapped_column(Integer)

    # QR Code details for profile access
    profile_qr_token: Mapped[str | None] = mapped_column(
        String(100), unique=True
    )  # For profile viewing
    qr_token: Mapped[str | None] = mapped_column(
        String(100), unique=True
    )  # For event login
    qr_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    qr_last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Contact information (one required for match contact purposes)
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(
        String(25)
    )  # Increased for formatted UK numbers
    fetlife_username: Mapped[str | None] = mapped_column(String(100))

    # Contact visibility flags
    contact_visible_to_matches: Mapped[bool] = mapped_column(Boolean, default=True)
    profile_visible: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # Controls public profile visibility

    # Registration status
    registration_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # Default true for free events

    # Special requirements or notes
    dietary_requirements: Mapped[str | None] = mapped_column(String(500))
    special_notes: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="attendee_profiles")
    event: Mapped["Event"] = relationship("Event", back_populates="attendees")

    # Matches as attendee1
    matches_as_attendee1: Mapped[list["Match"]] = relationship(
        "Match",
        foreign_keys="Match.attendee1_id",
        back_populates="attendee1",
        cascade="all, delete-orphan",
    )

    # Matches as attendee2
    matches_as_attendee2: Mapped[list["Match"]] = relationship(
        "Match",
        foreign_keys="Match.attendee2_id",
        back_populates="attendee2",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Attendee(id={self.id}, name={self.display_name}, category={self.category})>"

    @property
    def all_matches(self) -> list["Match"]:
        """Get all matches for this attendee."""
        return (self.matches_as_attendee1 or []) + (self.matches_as_attendee2 or [])

    def generate_qr_token(self) -> str:
        """Generate a unique QR token for event login."""
        import secrets

        self.qr_token = secrets.token_urlsafe(32)
        self.qr_generated_at = datetime.utcnow()
        return self.qr_token

    def generate_profile_qr_token(self) -> str:
        """Generate a unique QR token for profile viewing."""
        import secrets

        self.profile_qr_token = secrets.token_urlsafe(32)
        return self.profile_qr_token

    def has_contact_info(self) -> bool:
        """Check if attendee has at least one contact method."""
        return bool(self.contact_email or self.contact_phone or self.fetlife_username)

    def validate_contact_fields(self) -> None:
        """Validate contact information formats."""
        from app.utils.validators import (
            validate_email,
            validate_fetlife_username,
            validate_uk_phone_number,
        )

        if self.contact_email and not validate_email(self.contact_email):
            raise ValueError("Invalid email address format")

        if self.contact_phone and not validate_uk_phone_number(self.contact_phone):
            raise ValueError("Invalid UK phone number format")

        if self.fetlife_username and not validate_fetlife_username(
            self.fetlife_username
        ):
            raise ValueError("Invalid FetLife username format")

        # Ensure at least one contact method is provided
        if not self.has_contact_info():
            raise ValueError(
                "At least one contact method (email, phone, or FetLife username) must be provided"
            )

    def format_contact_fields(self) -> None:
        """Format contact fields to standard formats."""
        from app.utils.validators import format_uk_phone_number

        # Format phone number
        if self.contact_phone:
            self.contact_phone = format_uk_phone_number(self.contact_phone)

        # Clean up FetLife username (remove @ if present)
        if self.fetlife_username and self.fetlife_username.startswith("@"):
            self.fetlife_username = self.fetlife_username[1:]

    def validate_and_set_public_bio(self, bio: str) -> tuple[bool, str]:
        """
        Validate and set public bio with content filtering.

        Returns:
            Tuple of (success, message)
        """
        from app.utils.content_filter import bio_filter

        if not bio:
            self.public_bio = None
            return True, ""

        # Validate bio content
        is_valid, message = bio_filter.validate_bio(bio, max_length=500)

        if is_valid:
            self.public_bio = bio.strip()
            return True, "Bio updated successfully"
        else:
            return False, message

    def get_contact_info(
        self, requester_is_admin: bool = False, is_matched: bool = False
    ) -> dict:
        """
        Get contact information based on privacy settings.

        Args:
            requester_is_admin: Whether the requester is an event administrator
            is_matched: Whether the requester has a confirmed match with this attendee

        Returns:
            Dictionary with available contact information
        """
        contact_info = {}

        if requester_is_admin:
            # Administrators can see all contact info
            contact_info = {
                "email": self.contact_email,
                "phone": self.contact_phone,
                "fetlife_username": self.fetlife_username,
            }
        elif is_matched and self.contact_visible_to_matches:
            # Matched attendees can see contact info if visibility is enabled
            contact_info = {
                "email": self.contact_email,
                "phone": self.contact_phone,
                "fetlife_username": self.fetlife_username,
            }
        else:
            # No contact info visible
            contact_info = {"email": None, "phone": None, "fetlife_username": None}

        # Remove None values
        return {k: v for k, v in contact_info.items() if v is not None}

    def get_public_profile_data(
        self, requester_is_admin: bool = False, is_matched: bool = False
    ) -> dict:
        """
        Get public profile data based on privacy settings.

        Args:
            requester_is_admin: Whether the requester is an administrator
            is_matched: Whether the requester has a confirmed match with this attendee

        Returns:
            Dictionary with public profile information
        """
        if not self.profile_visible and not requester_is_admin:
            return {"profile_visible": False, "message": "This profile is private"}

        profile_data = {
            "id": str(self.id),
            "display_name": self.display_name,
            "age": self.age,
            "category": self.category.value,
            "public_bio": self.public_bio,
            "event_name": self.event.name if self.event else None,
            "profile_visible": True,
        }

        # Add contact info if appropriate
        contact_info = self.get_contact_info(requester_is_admin, is_matched)
        if contact_info:
            profile_data["contact_info"] = contact_info

        # Add admin-only info
        if requester_is_admin:
            profile_data.update(
                {
                    "checked_in": self.checked_in,
                    "registration_confirmed": self.registration_confirmed,
                    "payment_confirmed": self.payment_confirmed,
                    "registered_at": self.registered_at.isoformat(),
                    "private_bio": self.private_bio,
                    "dietary_requirements": self.dietary_requirements,
                    "special_notes": self.special_notes,
                }
            )

        return profile_data

    def is_interested_in_category(self, category: AttendeeCategory) -> bool:
        """Check if this attendee is interested in meeting the given category."""
        # This would be implemented with the preferences relationship
        # For now, we'll implement basic heterosexual matching logic
        if self.category == AttendeeCategory.TOP_MALE:
            return category in [
                AttendeeCategory.TOP_FEMALE,
                AttendeeCategory.BOTTOM_FEMALE,
            ]
        elif self.category == AttendeeCategory.TOP_FEMALE:
            return category in [AttendeeCategory.TOP_MALE, AttendeeCategory.BOTTOM_MALE]
        elif self.category == AttendeeCategory.BOTTOM_MALE:
            return category in [
                AttendeeCategory.TOP_FEMALE,
                AttendeeCategory.BOTTOM_FEMALE,
            ]
        elif self.category == AttendeeCategory.BOTTOM_FEMALE:
            return category in [AttendeeCategory.TOP_MALE, AttendeeCategory.BOTTOM_MALE]
        return False

    def can_match_with(self, other: "Attendee") -> bool:
        """Check if this attendee can be matched with another attendee."""
        if self.event_id != other.event_id:
            return False
        if self.id == other.id:
            return False

        # Check mutual interest
        return self.is_interested_in_category(
            other.category
        ) and other.is_interested_in_category(self.category)


class AttendeePreference(Base):
    """
    Explicit preference model for attendees to specify which categories they want to meet.
    This allows for more flexible matching beyond the basic category system.
    """

    __tablename__ = "attendee_preference"

    # Composite primary key
    attendee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendee.id", ondelete="CASCADE"), primary_key=True
    )
    preferred_category: Mapped[AttendeeCategory] = mapped_column(primary_key=True)

    # Preference strength (1-5 scale, 5 being most preferred)
    preference_strength: Mapped[int] = mapped_column(Integer, default=3)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    attendee: Mapped["Attendee"] = relationship("Attendee")

    def __repr__(self) -> str:
        return f"<AttendeePreference(attendee_id={self.attendee_id}, preferred={self.preferred_category})>"
