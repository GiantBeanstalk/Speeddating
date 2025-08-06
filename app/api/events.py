"""
Event Management API endpoints.

Handles event creation, management, and organizer dashboard functionality.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import current_active_organizer, current_active_user
from app.database import get_async_session
from app.models import (
    Attendee,
    AttendeeCategory,
    Event,
    EventStatus,
    Round,
    User,
)
from app.services import (
    connection_manager,
    countdown_manager,
    create_matching_service,
    create_qr_service,
)

router = APIRouter(prefix="/events", tags=["Events"])


# Pydantic models for requests/responses
class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    location: str | None = Field(None, max_length=500)
    event_date: datetime
    registration_deadline: datetime | None = None
    round_duration_minutes: int = Field(5, ge=1, le=60)
    break_duration_minutes: int = Field(2, ge=0, le=30)
    max_attendees: int = Field(100, ge=4, le=1000)
    min_attendees: int = Field(6, ge=4, le=100)
    ticket_price: int | None = Field(None, ge=0)  # Price in cents
    currency: str = Field("USD", min_length=3, max_length=3)


class EventUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    location: str | None = Field(None, max_length=500)
    event_date: datetime | None = None
    registration_deadline: datetime | None = None
    round_duration_minutes: int | None = Field(None, ge=1, le=60)
    break_duration_minutes: int | None = Field(None, ge=0, le=30)
    max_attendees: int | None = Field(None, ge=4, le=1000)
    min_attendees: int | None = Field(None, ge=4, le=100)
    ticket_price: int | None = Field(None, ge=0)
    currency: str | None = Field(None, min_length=3, max_length=3)


class EventResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    location: str | None
    event_date: datetime
    registration_deadline: datetime | None
    status: EventStatus
    attendee_count: int
    max_attendees: int
    min_attendees: int
    created_at: datetime
    organizer_name: str


class EventDashboard(BaseModel):
    event: EventResponse
    attendee_stats: dict[str, int]
    capacity_analysis: dict[str, Any]
    match_statistics: dict[str, int]
    qr_stats: dict[str, int]
    recent_registrations: list[dict[str, Any]]


class RoundCreate(BaseModel):
    round_number: int = Field(..., ge=1)
    name: str | None = Field(None, max_length=100)
    duration_minutes: int | None = Field(None, ge=1, le=60)
    break_after_minutes: int | None = Field(None, ge=0, le=30)


class AttendeeRegistration(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=200)
    category: AttendeeCategory
    age: int | None = Field(None, ge=18, le=100)
    bio: str | None = Field(None, max_length=1000)
    dietary_requirements: str | None = Field(None, max_length=500)
    contact_email: str | None = Field(None, max_length=320)
    contact_phone: str | None = Field(None, max_length=20)


@router.post("/", response_model=EventResponse)
async def create_event(
    event_data: EventCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Create a new event (organizer only)."""

    # Validate dates
    if (
        event_data.registration_deadline
        and event_data.registration_deadline >= event_data.event_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration deadline must be before event date",
        )

    if event_data.min_attendees > event_data.max_attendees:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Minimum attendees cannot exceed maximum attendees",
        )

    # Create event
    event = Event(organizer_id=current_user.id, **event_data.model_dump())

    # Generate QR secret key
    event.generate_qr_secret()

    session.add(event)
    await session.commit()
    await session.refresh(event)

    return EventResponse(
        id=event.id,
        name=event.name,
        description=event.description,
        location=event.location,
        event_date=event.event_date,
        registration_deadline=event.registration_deadline,
        status=event.status,
        attendee_count=0,
        max_attendees=event.max_attendees,
        min_attendees=event.min_attendees,
        created_at=event.created_at,
        organizer_name=current_user.full_name,
    )


@router.get("/", response_model=list[EventResponse])
async def get_events(
    status_filter: EventStatus | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Get events for the current organizer."""

    query = select(Event).where(Event.organizer_id == current_user.id)

    if status_filter:
        query = query.where(Event.status == status_filter)

    query = query.order_by(Event.event_date.desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    events = result.scalars().all()

    return [
        EventResponse(
            id=event.id,
            name=event.name,
            description=event.description,
            location=event.location,
            event_date=event.event_date,
            registration_deadline=event.registration_deadline,
            status=event.status,
            attendee_count=event.attendee_count,
            max_attendees=event.max_attendees,
            min_attendees=event.min_attendees,
            created_at=event.created_at,
            organizer_name=current_user.full_name,
        )
        for event in events
    ]


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Get a specific event."""

    result = await session.execute(
        select(Event).where(Event.id == event_id, Event.organizer_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    return EventResponse(
        id=event.id,
        name=event.name,
        description=event.description,
        location=event.location,
        event_date=event.event_date,
        registration_deadline=event.registration_deadline,
        status=event.status,
        attendee_count=event.attendee_count,
        max_attendees=event.max_attendees,
        min_attendees=event.min_attendees,
        created_at=event.created_at,
        organizer_name=current_user.full_name,
    )


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    event_data: EventUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Update an event."""

    result = await session.execute(
        select(Event).where(Event.id == event_id, Event.organizer_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # Update fields
    update_data = event_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)

    await session.commit()
    await session.refresh(event)

    return EventResponse(
        id=event.id,
        name=event.name,
        description=event.description,
        location=event.location,
        event_date=event.event_date,
        registration_deadline=event.registration_deadline,
        status=event.status,
        attendee_count=event.attendee_count,
        max_attendees=event.max_attendees,
        min_attendees=event.min_attendees,
        created_at=event.created_at,
        organizer_name=current_user.full_name,
    )


@router.post("/{event_id}/publish")
async def publish_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Publish an event to make it visible for registration."""

    result = await session.execute(
        select(Event).where(Event.id == event_id, Event.organizer_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    if event.status != EventStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft events can be published",
        )

    event.status = EventStatus.REGISTRATION_OPEN
    event.is_published = True

    await session.commit()

    return {"message": "Event published successfully"}


@router.get("/{event_id}/dashboard", response_model=EventDashboard)
async def get_event_dashboard(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Get comprehensive dashboard data for an event."""

    # Get event with all relationships
    result = await session.execute(
        select(Event)
        .options(
            selectinload(Event.attendees),
            selectinload(Event.rounds).selectinload(Round.matches),
            selectinload(Event.matches),
        )
        .where(Event.id == event_id, Event.organizer_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # Get attendee statistics
    attendee_stats = {}
    for category in AttendeeCategory:
        category_count = sum(
            1
            for a in event.attendees
            if a.category == category and a.registration_confirmed
        )
        attendee_stats[category.value] = category_count

    attendee_stats["total"] = sum(attendee_stats.values())
    attendee_stats["checked_in"] = sum(1 for a in event.attendees if a.checked_in)

    # Get capacity analysis using matching service
    matching_service = await create_matching_service(session)
    capacity_analysis = await matching_service.get_event_matching_summary(event_id)

    # Get match statistics
    match_stats = {
        "total_matches": len(event.matches),
        "completed_matches": sum(1 for m in event.matches if m.both_responded),
        "mutual_matches": sum(1 for m in event.matches if m.is_mutual_match),
        "pending_responses": sum(1 for m in event.matches if not m.both_responded),
    }

    # Get QR statistics
    qr_service = await create_qr_service(session)
    qr_stats = await qr_service.get_qr_token_stats(event_id)

    # Get recent registrations (last 10)
    recent_attendees = sorted(
        [a for a in event.attendees if a.registration_confirmed],
        key=lambda x: x.registered_at,
        reverse=True,
    )[:10]

    recent_registrations = [
        {
            "id": a.id,
            "display_name": a.display_name,
            "category": a.category.value,
            "registered_at": a.registered_at.isoformat(),
            "checked_in": a.checked_in,
        }
        for a in recent_attendees
    ]

    return EventDashboard(
        event=EventResponse(
            id=event.id,
            name=event.name,
            description=event.description,
            location=event.location,
            event_date=event.event_date,
            registration_deadline=event.registration_deadline,
            status=event.status,
            attendee_count=event.attendee_count,
            max_attendees=event.max_attendees,
            min_attendees=event.min_attendees,
            created_at=event.created_at,
            organizer_name=current_user.full_name,
        ),
        attendee_stats=attendee_stats,
        capacity_analysis=capacity_analysis,
        match_statistics=match_stats,
        qr_stats=qr_stats,
        recent_registrations=recent_registrations,
    )


@router.post("/{event_id}/rounds", response_model=dict)
async def create_event_rounds(
    event_id: uuid.UUID,
    total_rounds: int = Query(..., ge=1, le=20),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Create rounds for an event."""

    # Verify event ownership
    result = await session.execute(
        select(Event).where(Event.id == event_id, Event.organizer_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # Create rounds using matching service
    # matching_service = await create_matching_service(session)

    rounds = []
    for round_num in range(1, total_rounds + 1):
        round_obj = Round(
            event_id=event_id,
            round_number=round_num,
            name=f"Round {round_num}",
            duration_minutes=event.round_duration_minutes,
            break_after_minutes=event.break_duration_minutes,
        )
        rounds.append(round_obj)
        session.add(round_obj)

    await session.commit()

    return {
        "message": f"Created {total_rounds} rounds successfully",
        "rounds_created": total_rounds,
    }


@router.post("/{event_id}/rounds/{round_id}/matches")
async def create_round_matches(
    event_id: uuid.UUID,
    round_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Create matches for a specific round."""

    # Verify event ownership
    result = await session.execute(
        select(Event).where(Event.id == event_id, Event.organizer_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # Create matches using matching service
    matching_service = await create_matching_service(session)

    try:
        matches = await matching_service.create_round_matches(round_id)

        return {
            "message": f"Created {len(matches)} matches for the round",
            "matches_created": len(matches),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.delete("/{event_id}")
async def delete_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Delete an event (organizer only)."""

    result = await session.execute(
        select(Event).where(Event.id == event_id, Event.organizer_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    if event.status == EventStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an active event",
        )

    await session.delete(event)
    await session.commit()

    return {"message": "Event deleted successfully"}


# Event Countdown Endpoints


class CountdownStart(BaseModel):
    duration_minutes: int = Field(..., ge=1, le=60)
    message: str | None = Field(None, max_length=500)


class CountdownExtend(BaseModel):
    additional_minutes: int = Field(..., ge=1, le=30)


@router.post("/{event_id}/countdown/start")
async def start_event_countdown(
    event_id: uuid.UUID,
    countdown_data: CountdownStart,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Start countdown to event first round (organizer only)."""

    # Verify event ownership
    result = await session.execute(
        select(Event).where(Event.id == event_id, Event.organizer_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # Check if event is in appropriate state for countdown
    if event.status not in [
        EventStatus.REGISTRATION_CLOSED,
        EventStatus.REGISTRATION_OPEN,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start countdown for event with status {event.status.value}",
        )

    # Check if countdown is already active
    if event.countdown_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Countdown is already active for this event",
        )

    try:
        # Start countdown in event model
        event.start_countdown(
            duration_minutes=countdown_data.duration_minutes,
            message=countdown_data.message,
        )
        await session.commit()

        # Start real-time countdown manager
        await countdown_manager.start_event_countdown(
            event_id=event_id,
            duration_minutes=countdown_data.duration_minutes,
            message=countdown_data.message,
            session=session,
        )

        # Broadcast countdown start to all event participants
        await connection_manager.broadcast_to_event(
            {
                "type": "countdown_started",
                "event_id": str(event_id),
                "duration_minutes": countdown_data.duration_minutes,
                "message": countdown_data.message
                or f"Event starts in {countdown_data.duration_minutes} minutes!",
                "target_time": event.countdown_target_time.isoformat()
                if event.countdown_target_time
                else None,
            },
            event_id,
        )

        return {
            "message": "Countdown started successfully",
            "duration_minutes": countdown_data.duration_minutes,
            "target_time": event.countdown_target_time.isoformat()
            if event.countdown_target_time
            else None,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.post("/{event_id}/countdown/stop")
async def stop_event_countdown(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Stop active countdown (organizer only)."""

    # Verify event ownership
    result = await session.execute(
        select(Event).where(Event.id == event_id, Event.organizer_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    if not event.countdown_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active countdown to stop",
        )

    # Stop countdown in event model
    event.stop_countdown()
    await session.commit()

    # Stop real-time countdown manager
    await countdown_manager.stop_event_countdown(event_id)

    # Broadcast countdown cancellation
    await connection_manager.broadcast_to_event(
        {
            "type": "countdown_cancelled",
            "event_id": str(event_id),
            "message": "Countdown has been cancelled by the organizer.",
        },
        event_id,
    )

    return {"message": "Countdown stopped successfully"}


@router.post("/{event_id}/countdown/extend")
async def extend_event_countdown(
    event_id: uuid.UUID,
    extend_data: CountdownExtend,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Extend active countdown (organizer only)."""

    # Verify event ownership
    result = await session.execute(
        select(Event).where(Event.id == event_id, Event.organizer_id == current_user.id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    if not event.countdown_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active countdown to extend",
        )

    try:
        # Extend countdown in event model
        event.extend_countdown(extend_data.additional_minutes)
        await session.commit()

        # Extend real-time countdown manager
        await countdown_manager.extend_event_countdown(
            event_id=event_id, additional_minutes=extend_data.additional_minutes
        )

        return {
            "message": f"Countdown extended by {extend_data.additional_minutes} minutes",
            "new_target_time": event.countdown_target_time.isoformat()
            if event.countdown_target_time
            else None,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.get("/{event_id}/countdown/status")
async def get_event_countdown_status(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """Get current countdown status for an event."""

    # Get event (users can see countdown status for events they're attending)
    result = await session.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # Check if user has access to this event
    if not current_user.is_organizer or event.organizer_id != current_user.id:
        # Check if user is an attendee
        attendee_result = await session.execute(
            select(Attendee).where(
                and_(Attendee.event_id == event_id, Attendee.user_id == current_user.id)
            )
        )
        if not attendee_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view countdown for this event",
            )

    # Get countdown status from event model
    countdown_status = event.get_countdown_status()

    # Also get real-time status if available
    realtime_status = countdown_manager.get_countdown_status(event_id)
    if realtime_status:
        countdown_status.update(realtime_status)

    return {
        "event_id": str(event_id),
        "event_name": event.name,
        "countdown": countdown_status,
    }


@router.get("/active-countdowns")
async def get_active_countdowns(current_user: User = Depends(current_active_organizer)):
    """Get all active event countdowns (organizer only)."""

    active_countdowns = countdown_manager.get_all_active_countdowns()
    return {
        "active_countdowns": active_countdowns,
        "total_active": len(active_countdowns),
    }
