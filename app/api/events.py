"""
Event Management API endpoints.

Handles event creation, management, and organizer dashboard functionality.
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from app.database import get_async_session
from app.models import (
    User, Event, EventStatus, Attendee, AttendeeCategory, 
    Round, RoundStatus, Match, MatchResponse
)
from app.auth import current_active_organizer, current_active_user
from app.services import create_matching_service, create_qr_service, create_pdf_service


router = APIRouter(prefix="/events", tags=["Events"])


# Pydantic models for requests/responses
class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, max_length=500)
    event_date: datetime
    registration_deadline: Optional[datetime] = None
    round_duration_minutes: int = Field(5, ge=1, le=60)
    break_duration_minutes: int = Field(2, ge=0, le=30)
    max_attendees: int = Field(100, ge=4, le=1000)
    min_attendees: int = Field(6, ge=4, le=100)
    ticket_price: Optional[int] = Field(None, ge=0)  # Price in cents
    currency: str = Field("USD", min_length=3, max_length=3)


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, max_length=500)
    event_date: Optional[datetime] = None
    registration_deadline: Optional[datetime] = None
    round_duration_minutes: Optional[int] = Field(None, ge=1, le=60)
    break_duration_minutes: Optional[int] = Field(None, ge=0, le=30)
    max_attendees: Optional[int] = Field(None, ge=4, le=1000)
    min_attendees: Optional[int] = Field(None, ge=4, le=100)
    ticket_price: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)


class EventResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    location: Optional[str]
    event_date: datetime
    registration_deadline: Optional[datetime]
    status: EventStatus
    attendee_count: int
    max_attendees: int
    min_attendees: int
    created_at: datetime
    organizer_name: str


class EventDashboard(BaseModel):
    event: EventResponse
    attendee_stats: Dict[str, int]
    capacity_analysis: Dict[str, Any]
    match_statistics: Dict[str, int]
    qr_stats: Dict[str, int]
    recent_registrations: List[Dict[str, Any]]


class RoundCreate(BaseModel):
    round_number: int = Field(..., ge=1)
    name: Optional[str] = Field(None, max_length=100)
    duration_minutes: Optional[int] = Field(None, ge=1, le=60)
    break_after_minutes: Optional[int] = Field(None, ge=0, le=30)


class AttendeeRegistration(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=200)
    category: AttendeeCategory
    age: Optional[int] = Field(None, ge=18, le=100)
    bio: Optional[str] = Field(None, max_length=1000)
    dietary_requirements: Optional[str] = Field(None, max_length=500)
    contact_email: Optional[str] = Field(None, max_length=320)
    contact_phone: Optional[str] = Field(None, max_length=20)


@router.post("/", response_model=EventResponse)
async def create_event(
    event_data: EventCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer)
):
    """Create a new event (organizer only)."""
    
    # Validate dates
    if event_data.registration_deadline and event_data.registration_deadline >= event_data.event_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration deadline must be before event date"
        )
    
    if event_data.min_attendees > event_data.max_attendees:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Minimum attendees cannot exceed maximum attendees"
        )
    
    # Create event
    event = Event(
        organizer_id=current_user.id,
        **event_data.model_dump()
    )
    
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
        organizer_name=current_user.full_name
    )


@router.get("/", response_model=List[EventResponse])
async def get_events(
    status_filter: Optional[EventStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer)
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
            organizer_name=current_user.full_name
        )
        for event in events
    ]


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer)
):
    """Get a specific event."""
    
    result = await session.execute(
        select(Event).where(
            Event.id == event_id,
            Event.organizer_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
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
        organizer_name=current_user.full_name
    )


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    event_data: EventUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer)
):
    """Update an event."""
    
    result = await session.execute(
        select(Event).where(
            Event.id == event_id,
            Event.organizer_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
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
        organizer_name=current_user.full_name
    )


@router.post("/{event_id}/publish")
async def publish_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer)
):
    """Publish an event to make it visible for registration."""
    
    result = await session.execute(
        select(Event).where(
            Event.id == event_id,
            Event.organizer_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    if event.status != EventStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft events can be published"
        )
    
    event.status = EventStatus.REGISTRATION_OPEN
    event.is_published = True
    
    await session.commit()
    
    return {"message": "Event published successfully"}


@router.get("/{event_id}/dashboard", response_model=EventDashboard)
async def get_event_dashboard(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer)
):
    """Get comprehensive dashboard data for an event."""
    
    # Get event with all relationships
    result = await session.execute(
        select(Event)
        .options(
            selectinload(Event.attendees),
            selectinload(Event.rounds).selectinload(Round.matches),
            selectinload(Event.matches)
        )
        .where(
            Event.id == event_id,
            Event.organizer_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Get attendee statistics
    attendee_stats = {}
    for category in AttendeeCategory:
        category_count = sum(
            1 for a in event.attendees 
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
        "pending_responses": sum(1 for m in event.matches if not m.both_responded)
    }
    
    # Get QR statistics
    qr_service = await create_qr_service(session)
    qr_stats = await qr_service.get_qr_token_stats(event_id)
    
    # Get recent registrations (last 10)
    recent_attendees = sorted(
        [a for a in event.attendees if a.registration_confirmed],
        key=lambda x: x.registered_at,
        reverse=True
    )[:10]
    
    recent_registrations = [
        {
            "id": a.id,
            "display_name": a.display_name,
            "category": a.category.value,
            "registered_at": a.registered_at.isoformat(),
            "checked_in": a.checked_in
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
            organizer_name=current_user.full_name
        ),
        attendee_stats=attendee_stats,
        capacity_analysis=capacity_analysis,
        match_statistics=match_stats,
        qr_stats=qr_stats,
        recent_registrations=recent_registrations
    )


@router.post("/{event_id}/rounds", response_model=dict)
async def create_event_rounds(
    event_id: uuid.UUID,
    total_rounds: int = Query(..., ge=1, le=20),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer)
):
    """Create rounds for an event."""
    
    # Verify event ownership
    result = await session.execute(
        select(Event).where(
            Event.id == event_id,
            Event.organizer_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Create rounds using matching service
    matching_service = await create_matching_service(session)
    
    rounds = []
    for round_num in range(1, total_rounds + 1):
        round_obj = Round(
            event_id=event_id,
            round_number=round_num,
            name=f"Round {round_num}",
            duration_minutes=event.round_duration_minutes,
            break_after_minutes=event.break_duration_minutes
        )
        rounds.append(round_obj)
        session.add(round_obj)
    
    await session.commit()
    
    return {
        "message": f"Created {total_rounds} rounds successfully",
        "rounds_created": total_rounds
    }


@router.post("/{event_id}/rounds/{round_id}/matches")
async def create_round_matches(
    event_id: uuid.UUID,
    round_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer)
):
    """Create matches for a specific round."""
    
    # Verify event ownership
    result = await session.execute(
        select(Event).where(
            Event.id == event_id,
            Event.organizer_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Create matches using matching service
    matching_service = await create_matching_service(session)
    
    try:
        matches = await matching_service.create_round_matches(round_id)
        
        return {
            "message": f"Created {len(matches)} matches for the round",
            "matches_created": len(matches)
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{event_id}")
async def delete_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer)
):
    """Delete an event (organizer only)."""
    
    result = await session.execute(
        select(Event).where(
            Event.id == event_id,
            Event.organizer_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    if event.status == EventStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an active event"
        )
    
    await session.delete(event)
    await session.commit()
    
    return {"message": "Event deleted successfully"}