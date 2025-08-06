"""
Round Management API endpoints.

Handles round creation, timing, and real-time management for speed dating events.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import current_active_organizer
from app.database import get_async_session
from app.models import Event, Round, RoundStatus, User
from app.services import create_matching_service
from app.services.websocket_manager import connection_manager, timer_manager

router = APIRouter(prefix="/rounds", tags=["Rounds"])


# Pydantic models
class RoundCreate(BaseModel):
    round_number: int = Field(..., ge=1, le=50)
    name: str | None = Field(None, max_length=100)
    duration_minutes: int = Field(5, ge=1, le=60)
    break_after_minutes: int = Field(2, ge=0, le=30)
    scheduled_start: datetime | None = None


class RoundUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    duration_minutes: int | None = Field(None, ge=1, le=60)
    break_after_minutes: int | None = Field(None, ge=0, le=30)
    scheduled_start: datetime | None = None
    announcements: str | None = Field(None, max_length=1000)
    notes: str | None = Field(None, max_length=500)


class RoundResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    round_number: int
    name: str | None
    status: RoundStatus
    duration_minutes: int
    break_after_minutes: int
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    is_break_active: bool
    total_matches: int
    completed_matches: int
    completion_percentage: float
    time_remaining: int | None  # seconds
    announcements: str | None
    created_at: datetime


class RoundTimer(BaseModel):
    round_id: uuid.UUID
    status: RoundStatus
    time_remaining: int  # seconds
    total_duration: int  # seconds
    is_break: bool
    break_time_remaining: int | None  # seconds if in break


class BulkRoundCreate(BaseModel):
    total_rounds: int = Field(..., ge=1, le=20)
    duration_minutes: int = Field(5, ge=1, le=60)
    break_duration_minutes: int = Field(2, ge=0, le=30)
    start_time: datetime | None = None


# In-memory store for active timers (in production, use Redis)
active_timers: dict[uuid.UUID, dict[str, Any]] = {}


def calculate_round_times(round_obj: Round) -> dict[str, int | None]:
    """Calculate time remaining and other timing information for a round."""
    now = datetime.utcnow()

    if round_obj.status == RoundStatus.PENDING:
        return {
            "time_remaining": None,
            "break_time_remaining": None,
            "total_elapsed": 0,
        }

    if not round_obj.actual_start:
        return {
            "time_remaining": None,
            "break_time_remaining": None,
            "total_elapsed": 0,
        }

    elapsed = (now - round_obj.actual_start).total_seconds()
    round_duration_seconds = round_obj.duration_minutes * 60
    break_duration_seconds = round_obj.break_after_minutes * 60

    if round_obj.status == RoundStatus.ACTIVE:
        time_remaining = max(0, round_duration_seconds - elapsed)
        return {
            "time_remaining": int(time_remaining),
            "break_time_remaining": None,
            "total_elapsed": int(elapsed),
        }

    elif round_obj.status == RoundStatus.BREAK:
        # Calculate break time (assumes break started when round ended)
        break_start = round_obj.actual_start + timedelta(seconds=round_duration_seconds)
        break_elapsed = (now - break_start).total_seconds()
        break_time_remaining = max(0, break_duration_seconds - break_elapsed)

        return {
            "time_remaining": 0,
            "break_time_remaining": int(break_time_remaining),
            "total_elapsed": int(elapsed),
        }

    else:  # COMPLETED or CANCELLED
        return {
            "time_remaining": 0,
            "break_time_remaining": 0,
            "total_elapsed": int(elapsed),
        }


@router.post("/event/{event_id}/bulk-create")
async def create_bulk_rounds(
    event_id: uuid.UUID,
    round_data: BulkRoundCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Create multiple rounds for an event."""

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

    # Check if rounds already exist
    existing_rounds = await session.execute(
        select(Round).where(Round.event_id == event_id)
    )
    if existing_rounds.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rounds already exist for this event",
        )

    # Create rounds
    rounds = []
    current_start = round_data.start_time or datetime.utcnow()

    for round_num in range(1, round_data.total_rounds + 1):
        scheduled_start = current_start + timedelta(
            minutes=(round_num - 1)
            * (round_data.duration_minutes + round_data.break_duration_minutes)
        )

        round_obj = Round(
            event_id=event_id,
            round_number=round_num,
            name=f"Round {round_num}",
            duration_minutes=round_data.duration_minutes,
            break_after_minutes=round_data.break_duration_minutes,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_start
            + timedelta(minutes=round_data.duration_minutes),
        )
        rounds.append(round_obj)
        session.add(round_obj)

    await session.commit()

    return {
        "message": f"Created {round_data.total_rounds} rounds successfully",
        "rounds_created": round_data.total_rounds,
        "first_round_starts": rounds[0].scheduled_start.isoformat() if rounds else None,
    }


@router.get("/event/{event_id}", response_model=list[RoundResponse])
async def get_event_rounds(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Get all rounds for an event."""

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

    # Get rounds with match counts
    rounds_result = await session.execute(
        select(Round)
        .options(selectinload(Round.matches))
        .where(Round.event_id == event_id)
        .order_by(Round.round_number)
    )
    rounds = rounds_result.scalars().all()

    round_responses = []
    for round_obj in rounds:
        timing_info = calculate_round_times(round_obj)

        round_responses.append(
            RoundResponse(
                id=round_obj.id,
                event_id=round_obj.event_id,
                round_number=round_obj.round_number,
                name=round_obj.name,
                status=round_obj.status,
                duration_minutes=round_obj.duration_minutes,
                break_after_minutes=round_obj.break_after_minutes,
                scheduled_start=round_obj.scheduled_start,
                scheduled_end=round_obj.scheduled_end,
                actual_start=round_obj.actual_start,
                actual_end=round_obj.actual_end,
                is_break_active=round_obj.is_break_active,
                total_matches=round_obj.total_matches,
                completed_matches=round_obj.completed_matches,
                completion_percentage=round_obj.completion_percentage,
                time_remaining=timing_info["time_remaining"],
                announcements=round_obj.announcements,
                created_at=round_obj.created_at,
            )
        )

    return round_responses


@router.get("/{round_id}", response_model=RoundResponse)
async def get_round(
    round_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Get a specific round."""

    round_result = await session.execute(
        select(Round)
        .options(selectinload(Round.event), selectinload(Round.matches))
        .where(Round.id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )

    # Verify event ownership
    if round_obj.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this round",
        )

    timing_info = calculate_round_times(round_obj)

    return RoundResponse(
        id=round_obj.id,
        event_id=round_obj.event_id,
        round_number=round_obj.round_number,
        name=round_obj.name,
        status=round_obj.status,
        duration_minutes=round_obj.duration_minutes,
        break_after_minutes=round_obj.break_after_minutes,
        scheduled_start=round_obj.scheduled_start,
        scheduled_end=round_obj.scheduled_end,
        actual_start=round_obj.actual_start,
        actual_end=round_obj.actual_end,
        is_break_active=round_obj.is_break_active,
        total_matches=round_obj.total_matches,
        completed_matches=round_obj.completed_matches,
        completion_percentage=round_obj.completion_percentage,
        time_remaining=timing_info["time_remaining"],
        announcements=round_obj.announcements,
        created_at=round_obj.created_at,
    )


@router.post("/{round_id}/start")
async def start_round(
    round_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Start a round."""

    round_result = await session.execute(
        select(Round).options(selectinload(Round.event)).where(Round.id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )

    # Verify event ownership
    if round_obj.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to start this round",
        )

    if round_obj.status != RoundStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Round is already {round_obj.status.value}",
        )

    # Start the round
    round_obj.start_round()

    # Create matches if they don't exist
    if not round_obj.matches:
        matching_service = await create_matching_service(session)
        try:
            await matching_service.create_round_matches(round_id)
        except ValueError as e:
            # Rollback the round start if match creation fails
            round_obj.status = RoundStatus.PENDING
            round_obj.actual_start = None
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create matches: {str(e)}",
            ) from e

    await session.commit()

    # Start real-time timer
    await timer_manager.start_round_timer(
        round_id=round_id,
        duration_minutes=round_obj.duration_minutes,
        break_minutes=round_obj.break_after_minutes,
        session=session,
    )

    # Broadcast round start to event room
    await connection_manager.broadcast_to_event(
        {
            "type": "round_started",
            "round_id": str(round_id),
            "round_number": round_obj.round_number,
            "duration_minutes": round_obj.duration_minutes,
            "message": f"Round {round_obj.round_number} has started!",
        },
        round_obj.event_id,
    )

    return {
        "message": "Round started successfully",
        "round_id": round_id,
        "started_at": round_obj.actual_start.isoformat(),
        "duration_minutes": round_obj.duration_minutes,
    }


@router.post("/{round_id}/end")
async def end_round(
    round_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """End a round manually."""

    round_result = await session.execute(
        select(Round).options(selectinload(Round.event)).where(Round.id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )

    # Verify event ownership
    if round_obj.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to end this round",
        )

    if round_obj.status not in [RoundStatus.ACTIVE, RoundStatus.BREAK]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot end round with status {round_obj.status.value}",
        )

    # End the round
    round_obj.end_round()
    await session.commit()

    # Stop real-time timer
    await timer_manager.stop_round_timer(round_id)

    # Broadcast round end to event room
    await connection_manager.broadcast_to_event(
        {
            "type": "round_ended",
            "round_id": str(round_id),
            "round_number": round_obj.round_number,
            "message": f"Round {round_obj.round_number} has ended.",
        },
        round_obj.event_id,
    )

    return {
        "message": "Round ended successfully",
        "round_id": round_id,
        "ended_at": round_obj.actual_end.isoformat() if round_obj.actual_end else None,
    }


@router.post("/{round_id}/break")
async def start_break(
    round_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Start break period for a round."""

    round_result = await session.execute(
        select(Round).options(selectinload(Round.event)).where(Round.id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )

    # Verify event ownership
    if round_obj.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this round",
        )

    if round_obj.status != RoundStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only start break from active round",
        )

    # Start break
    round_obj.start_break()
    await session.commit()

    # The timer manager will automatically handle the break timing
    # Broadcast break start to event room
    await connection_manager.broadcast_to_event(
        {
            "type": "break_started",
            "round_id": str(round_id),
            "round_number": round_obj.round_number,
            "break_duration_minutes": round_obj.break_after_minutes,
            "message": f"Break time! {round_obj.break_after_minutes} minutes until next round.",
        },
        round_obj.event_id,
    )

    return {
        "message": "Break started successfully",
        "round_id": round_id,
        "break_duration_minutes": round_obj.break_after_minutes,
    }


@router.get("/{round_id}/timer", response_model=RoundTimer)
async def get_round_timer(
    round_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Get real-time timer information for a round."""

    round_result = await session.execute(
        select(Round).options(selectinload(Round.event)).where(Round.id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )

    # Verify event ownership
    if round_obj.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this round",
        )

    timing_info = calculate_round_times(round_obj)

    return RoundTimer(
        round_id=round_id,
        status=round_obj.status,
        time_remaining=timing_info["time_remaining"] or 0,
        total_duration=round_obj.duration_minutes * 60,
        is_break=round_obj.is_break_active,
        break_time_remaining=timing_info["break_time_remaining"],
    )


@router.put("/{round_id}")
async def update_round(
    round_id: uuid.UUID,
    round_data: RoundUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Update round information."""

    round_result = await session.execute(
        select(Round).options(selectinload(Round.event)).where(Round.id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )

    # Verify event ownership
    if round_obj.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this round",
        )

    # Don't allow updates to active or completed rounds
    if round_obj.status in [RoundStatus.ACTIVE, RoundStatus.COMPLETED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update active or completed rounds",
        )

    # Update fields
    update_data = round_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(round_obj, field, value)

    # Update scheduled end if start time or duration changed
    if round_obj.scheduled_start and round_obj.duration_minutes:
        round_obj.scheduled_end = round_obj.scheduled_start + timedelta(
            minutes=round_obj.duration_minutes
        )

    await session.commit()

    return {"message": "Round updated successfully"}


@router.post("/{round_id}/announce")
async def make_round_announcement(
    round_id: uuid.UUID,
    announcement: dict,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Make an announcement to all participants in a round."""

    round_result = await session.execute(
        select(Round).options(selectinload(Round.event)).where(Round.id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )

    # Verify event ownership
    if round_obj.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to make announcements for this round",
        )

    message = announcement.get("message", "")
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Announcement message is required",
        )

    # Broadcast announcement to round timer subscribers
    await connection_manager.broadcast_to_round_timer(
        {
            "type": "announcement",
            "round_id": str(round_id),
            "message": message,
            "from_organizer": True,
            "organizer_name": current_user.email,
        },
        round_id,
    )

    # Also broadcast to event room
    await connection_manager.broadcast_to_event(
        {
            "type": "round_announcement",
            "round_id": str(round_id),
            "round_number": round_obj.round_number,
            "message": message,
            "from_organizer": True,
        },
        round_obj.event_id,
    )

    return {"message": "Announcement sent successfully"}


@router.get("/active-timers")
async def get_active_timers(current_user: User = Depends(current_active_organizer)):
    """Get all active round timers (organizer only)."""

    active_timers = timer_manager.get_all_active_timers()
    return {"active_timers": active_timers, "total_active": len(active_timers)}


@router.post("/{round_id}/extend")
async def extend_round_time(
    round_id: uuid.UUID,
    extension_data: dict,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Extend the time of an active round."""

    round_result = await session.execute(
        select(Round).options(selectinload(Round.event)).where(Round.id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()

    if not round_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Round not found"
        )

    # Verify event ownership
    if round_obj.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to extend this round",
        )

    if round_obj.status != RoundStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only extend active rounds",
        )

    additional_minutes = extension_data.get("additional_minutes", 0)
    if additional_minutes <= 0 or additional_minutes > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Additional minutes must be between 1 and 30",
        )

    # Update round duration
    round_obj.duration_minutes += additional_minutes
    await session.commit()

    # Broadcast extension to participants
    await connection_manager.broadcast_to_round_timer(
        {
            "type": "round_extended",
            "round_id": str(round_id),
            "additional_minutes": additional_minutes,
            "new_duration": round_obj.duration_minutes,
            "message": f"Round extended by {additional_minutes} minutes!",
        },
        round_id,
    )

    await connection_manager.broadcast_to_event(
        {
            "type": "round_extended",
            "round_id": str(round_id),
            "round_number": round_obj.round_number,
            "additional_minutes": additional_minutes,
            "message": f"Round {round_obj.round_number} extended by {additional_minutes} minutes",
        },
        round_obj.event_id,
    )

    return {
        "message": f"Round extended by {additional_minutes} minutes",
        "new_duration": round_obj.duration_minutes,
    }


# Background task functions
async def schedule_round_end(round_id: uuid.UUID, duration_minutes: int):
    """Background task to automatically end a round after its duration."""
    await asyncio.sleep(duration_minutes * 60)

    # This would need a database connection in the background task
    # In production, this should be handled by a task queue like Celery
    pass


async def schedule_break_end(round_id: uuid.UUID, break_minutes: int):
    """Background task to automatically end a break period."""
    await asyncio.sleep(break_minutes * 60)

    # This would need a database connection in the background task
    # In production, this should be handled by a task queue like Celery
    pass
