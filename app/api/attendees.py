"""
Attendee Management API endpoints.

Handles attendee registration, check-in, and management functionality.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import current_active_organizer, current_active_user
from app.database import get_async_session
from app.models import (
    Attendee,
    AttendeeCategory,
    Event,
    EventStatus,
    Match,
    MatchResponse,
    User,
)
from app.utils.content_filter import bio_filter
from app.utils.validators import ContactValidationMixin

router = APIRouter(prefix="/attendees", tags=["Attendees"])


# Pydantic models
class AttendeeRegistration(BaseModel, ContactValidationMixin):
    display_name: str = Field(..., min_length=1, max_length=200)
    category: AttendeeCategory
    age: int | None = Field(None, ge=18, le=100)
    public_bio: str | None = Field(
        None, max_length=500, description="Public bio visible to other attendees"
    )
    dietary_requirements: str | None = Field(None, max_length=500)

    # Contact information - at least one required
    contact_email: str | None = Field(None, max_length=320)
    contact_phone: str | None = Field(
        None, max_length=25
    )  # Increased for formatted numbers
    fetlife_username: str | None = Field(None, max_length=100)
    contact_visible_to_matches: bool = Field(True)
    profile_visible: bool = Field(
        True, description="Whether profile is visible to others"
    )

    def validate_contact_info(self):
        """Validate that at least one contact method is provided."""
        if not (self.contact_email or self.contact_phone or self.fetlife_username):
            raise ValueError(
                "At least one contact method (email, phone, or FetLife username) must be provided"
            )

    def validate_public_bio(self):
        """Validate public bio content."""
        if self.public_bio:
            is_valid, message = bio_filter.validate_bio(self.public_bio, max_length=500)
            if not is_valid:
                raise ValueError(message)


class AttendeeResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    event_id: uuid.UUID
    display_name: str
    category: AttendeeCategory
    age: int | None
    bio: str | None
    checked_in: bool
    check_in_time: datetime | None
    table_number: int | None
    registration_confirmed: bool
    payment_confirmed: bool
    registered_at: datetime

    # Contact info (visibility controlled by privacy settings)
    contact_email: str | None = None
    contact_phone: str | None = None
    fetlife_username: str | None = None


class AttendeeUpdate(BaseModel, ContactValidationMixin):
    display_name: str | None = Field(None, min_length=1, max_length=200)
    age: int | None = Field(None, ge=18, le=100)
    bio: str | None = Field(None, max_length=1000)
    dietary_requirements: str | None = Field(None, max_length=500)

    # Contact information
    contact_email: str | None = Field(None, max_length=320)
    contact_phone: str | None = Field(
        None, max_length=25
    )  # Increased for formatted numbers
    fetlife_username: str | None = Field(None, max_length=100)
    contact_visible_to_matches: bool | None = None


class CheckInRequest(BaseModel):
    table_number: int | None = Field(None, ge=1, le=100)


def build_attendee_response(
    attendee: Attendee, current_user: User, is_matched: bool = False
) -> AttendeeResponse:
    """Build AttendeeResponse with appropriate contact info visibility."""

    # Determine if current user can see contact info
    is_admin = current_user.is_organizer or current_user.is_superuser
    contact_info = attendee.get_contact_info(
        requester_is_admin=is_admin, is_matched=is_matched
    )

    return AttendeeResponse(
        id=attendee.id,
        user_id=attendee.user_id,
        event_id=attendee.event_id,
        display_name=attendee.display_name,
        category=attendee.category,
        age=attendee.age,
        bio=attendee.bio,
        checked_in=attendee.checked_in,
        check_in_time=attendee.check_in_time,
        table_number=attendee.table_number,
        registration_confirmed=attendee.registration_confirmed,
        payment_confirmed=attendee.payment_confirmed,
        registered_at=attendee.registered_at,
        contact_email=contact_info.get("contact_email"),
        contact_phone=contact_info.get("contact_phone"),
        fetlife_username=contact_info.get("fetlife_username"),
    )


class MatchResponseRequest(BaseModel):
    response: MatchResponse
    notes: str | None = Field(None, max_length=1000)
    rating: int | None = Field(None, ge=1, le=5)


class PaymentConfirmationRequest(BaseModel):
    payment_confirmed: bool
    payment_method: str | None = Field(None, max_length=100)
    payment_reference: str | None = Field(None, max_length=200)


@router.post("/register/{event_id}", response_model=AttendeeResponse)
async def register_for_event(
    event_id: uuid.UUID,
    registration_data: AttendeeRegistration,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """Register current user as an attendee for an event."""

    # Check if event exists and registration is open
    result = await session.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    if not event.is_registration_open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration is not open for this event",
        )

    if event.is_full:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event is at maximum capacity",
        )

    # Validate contact information and bio
    try:
        registration_data.validate_contact_info()
        registration_data.validate_public_bio()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    # Check if user is already registered
    existing_result = await session.execute(
        select(Attendee).where(
            and_(Attendee.user_id == current_user.id, Attendee.event_id == event_id)
        )
    )
    existing_attendee = existing_result.scalar_one_or_none()

    if existing_attendee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already registered for this event",
        )

    # Create attendee record
    attendee = Attendee(
        user_id=current_user.id, event_id=event_id, **registration_data.model_dump()
    )

    # Format and validate contact fields
    try:
        attendee.format_contact_fields()
        attendee.validate_contact_fields()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    # Generate QR token
    attendee.generate_qr_token()

    session.add(attendee)
    await session.commit()
    await session.refresh(attendee)

    return build_attendee_response(attendee, current_user)


@router.get("/my-registrations", response_model=list[AttendeeResponse])
async def get_my_registrations(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """Get all event registrations for the current user."""

    result = await session.execute(
        select(Attendee)
        .where(Attendee.user_id == current_user.id)
        .order_by(Attendee.registered_at.desc())
    )
    attendees = result.scalars().all()

    return [build_attendee_response(attendee, current_user) for attendee in attendees]


@router.get("/event/{event_id}", response_model=list[AttendeeResponse])
async def get_event_attendees(
    event_id: uuid.UUID,
    category: AttendeeCategory | None = Query(None),
    checked_in_only: bool = Query(False),
    confirmed_only: bool = Query(True),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Get attendees for an event (organizer only)."""

    # Verify event ownership
    event_result = await session.execute(
        select(Event).where(
            and_(Event.id == event_id, Event.organizer_id == current_user.id)
        )
    )
    event = event_result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # Build query
    query = select(Attendee).where(Attendee.event_id == event_id)

    if category:
        query = query.where(Attendee.category == category)

    if checked_in_only:
        query = query.where(Attendee.checked_in)

    if confirmed_only:
        query = query.where(Attendee.registration_confirmed)

    query = query.order_by(Attendee.registered_at)

    result = await session.execute(query)
    attendees = result.scalars().all()

    return [build_attendee_response(attendee, current_user) for attendee in attendees]


@router.put("/{attendee_id}", response_model=AttendeeResponse)
async def update_attendee(
    attendee_id: uuid.UUID,
    update_data: AttendeeUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """Update attendee information."""

    # Get attendee
    result = await session.execute(select(Attendee).where(Attendee.id == attendee_id))
    attendee = result.scalar_one_or_none()

    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendee not found"
        )

    # Check if user owns this attendee record or is event organizer
    if attendee.user_id != current_user.id:
        # Check if user is the event organizer
        event_result = await session.execute(
            select(Event).where(Event.id == attendee.event_id)
        )
        event = event_result.scalar_one_or_none()

        if not event or event.organizer_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this attendee",
            )

    # Update fields
    update_fields = update_data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(attendee, field, value)

    # Format and validate contact fields if any were updated
    contact_fields = {"contact_email", "contact_phone", "fetlife_username"}
    if any(field in update_fields for field in contact_fields):
        try:
            attendee.format_contact_fields()
            # Only validate if we have at least one contact method (allow clearing fields)
            if attendee.has_contact_info():
                attendee.validate_contact_fields()
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e

    await session.commit()
    await session.refresh(attendee)

    return build_attendee_response(attendee, current_user)


@router.post("/{attendee_id}/check-in")
async def check_in_attendee(
    attendee_id: uuid.UUID,
    check_in_data: CheckInRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Check in an attendee (organizer only)."""

    # Get attendee with event
    result = await session.execute(
        select(Attendee)
        .options(selectinload(Attendee.event))
        .where(Attendee.id == attendee_id)
    )
    attendee = result.scalar_one_or_none()

    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendee not found"
        )

    # Verify organizer owns the event
    if attendee.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to check in this attendee",
        )

    if attendee.checked_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendee is already checked in",
        )

    # Check in attendee
    attendee.checked_in = True
    attendee.check_in_time = datetime.utcnow()
    if check_in_data.table_number:
        attendee.table_number = check_in_data.table_number

    await session.commit()

    return {"message": "Attendee checked in successfully"}


@router.delete("/{attendee_id}/check-in")
async def check_out_attendee(
    attendee_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Check out an attendee (organizer only)."""

    # Get attendee with event
    result = await session.execute(
        select(Attendee)
        .options(selectinload(Attendee.event))
        .where(Attendee.id == attendee_id)
    )
    attendee = result.scalar_one_or_none()

    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendee not found"
        )

    # Verify organizer owns the event
    if attendee.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this attendee",
        )

    # Check out attendee
    attendee.checked_in = False
    attendee.check_in_time = None
    attendee.table_number = None

    await session.commit()

    return {"message": "Attendee checked out successfully"}


@router.post("/{attendee_id}/payment")
async def confirm_payment(
    attendee_id: uuid.UUID,
    payment_data: PaymentConfirmationRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Confirm payment for an attendee (organizer only)."""

    # Get attendee with event
    result = await session.execute(
        select(Attendee)
        .options(selectinload(Attendee.event))
        .where(Attendee.id == attendee_id)
    )
    attendee = result.scalar_one_or_none()

    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendee not found"
        )

    # Verify organizer owns the event
    if attendee.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify payment status for this attendee",
        )

    # Update payment status
    attendee.payment_confirmed = payment_data.payment_confirmed

    # Auto-confirm registration if payment is confirmed
    if payment_data.payment_confirmed and not attendee.registration_confirmed:
        attendee.registration_confirmed = True

    await session.commit()

    status_message = (
        "confirmed" if payment_data.payment_confirmed else "marked as unpaid"
    )
    return {"message": f"Payment {status_message} successfully"}


@router.get("/{attendee_id}/matches")
async def get_attendee_matches(
    attendee_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """Get matches for an attendee."""

    # Get attendee
    result = await session.execute(select(Attendee).where(Attendee.id == attendee_id))
    attendee = result.scalar_one_or_none()

    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendee not found"
        )

    # Check authorization (attendee owner or event organizer)
    if attendee.user_id != current_user.id:
        event_result = await session.execute(
            select(Event).where(Event.id == attendee.event_id)
        )
        event = event_result.scalar_one_or_none()

        if not event or event.organizer_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view these matches",
            )

    # Get matches where attendee is participant
    matches_result = await session.execute(
        select(Match)
        .options(
            selectinload(Match.attendee1),
            selectinload(Match.attendee2),
            selectinload(Match.round),
        )
        .where(
            or_(Match.attendee1_id == attendee_id, Match.attendee2_id == attendee_id)
        )
        .order_by(Match.created_at)
    )
    matches = matches_result.scalars().all()

    match_data = []
    for match in matches:
        # Determine which attendee is the "other" one
        other_attendee = (
            match.attendee2 if match.attendee1_id == attendee_id else match.attendee1
        )
        my_response = (
            match.attendee1_response
            if match.attendee1_id == attendee_id
            else match.attendee2_response
        )
        their_response = (
            match.attendee2_response
            if match.attendee1_id == attendee_id
            else match.attendee1_response
        )

        # Get contact info if this is a mutual match
        contact_info = {}
        if match.is_mutual_match:
            contact_info = other_attendee.get_contact_info(
                requester_is_admin=False, is_matched=True
            )

        other_attendee_data = {
            "id": other_attendee.id,
            "display_name": other_attendee.display_name,
            "category": other_attendee.category.value,
            "age": other_attendee.age,
        }

        # Add contact info if available
        if contact_info:
            other_attendee_data.update(contact_info)

        match_data.append(
            {
                "match_id": match.id,
                "round_number": match.round.round_number if match.round else None,
                "table_number": match.table_number,
                "other_attendee": other_attendee_data,
                "my_response": my_response.value if my_response else None,
                "their_response": their_response.value if their_response else None,
                "is_mutual_match": match.is_mutual_match,
                "match_completed": match.both_responded,
                "created_at": match.created_at.isoformat(),
            }
        )

    return {
        "attendee_id": attendee_id,
        "total_matches": len(match_data),
        "completed_responses": sum(
            1 for m in match_data if m["my_response"] != "NO_RESPONSE"
        ),
        "mutual_matches": sum(1 for m in match_data if m["is_mutual_match"]),
        "matches": match_data,
    }


@router.post("/matches/{match_id}/respond")
async def respond_to_match(
    match_id: uuid.UUID,
    response_data: MatchResponseRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """Respond to a match."""

    # Get match with attendees
    result = await session.execute(
        select(Match)
        .options(selectinload(Match.attendee1), selectinload(Match.attendee2))
        .where(Match.id == match_id)
    )
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found"
        )

    # Determine which attendee is responding
    attendee_id = None
    if match.attendee1.user_id == current_user.id:
        attendee_id = match.attendee1_id
    elif match.attendee2.user_id == current_user.id:
        attendee_id = match.attendee2_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to respond to this match",
        )

    # Set the response
    success = match.set_attendee_response(
        attendee_id=attendee_id,
        response=response_data.response,
        notes=response_data.notes,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not set response for this match",
        )

    await session.commit()

    return {
        "message": "Response recorded successfully",
        "is_mutual_match": match.is_mutual_match,
        "both_responded": match.both_responded,
    }


@router.delete("/{attendee_id}")
async def withdraw_registration(
    attendee_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """Withdraw from an event (delete attendee registration)."""

    # Get attendee
    result = await session.execute(select(Attendee).where(Attendee.id == attendee_id))
    attendee = result.scalar_one_or_none()

    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendee not found"
        )

    # Check authorization
    if attendee.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to withdraw this registration",
        )

    # Check if event has started
    event_result = await session.execute(
        select(Event).where(Event.id == attendee.event_id)
    )
    event = event_result.scalar_one_or_none()

    if event and event.status == EventStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot withdraw from an active event",
        )

    await session.delete(attendee)
    await session.commit()

    return {"message": "Registration withdrawn successfully"}
