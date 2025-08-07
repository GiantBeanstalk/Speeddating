"""
Template rendering routes for HTML interface.

Provides server-side rendering of HTML templates with data from the API.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import current_active_organizer, current_active_user
from app.database import get_async_session
from app.models import Attendee, Event, EventStatus, Match, MatchResponse, User
from app.security import add_csrf_to_templates, super_user_manager

router = APIRouter(tags=["Templates"])

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# Add CSRF protection to templates
add_csrf_to_templates(templates)


# Authentication Templates
@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page."""
    return templates.TemplateResponse(
        "auth/login.html", 
        {"request": request, "current_year": datetime.now().year}
    )


@router.get("/auth/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Display forgot password page."""
    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {"request": request, "current_year": datetime.now().year}
    )


@router.get("/auth/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    """Display reset password page for a specific token."""
    return templates.TemplateResponse(
        "auth/reset_password.html",
        {"request": request, "token": token, "current_year": datetime.now().year}
    )


# Admin Templates
@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Admin dashboard with event and system statistics."""
    try:
        # Get dashboard statistics
        stats = await get_admin_dashboard_stats(session)
        
        # Get recent events
        recent_events_result = await session.execute(
            select(Event)
            .options(selectinload(Event.attendees))
            .order_by(Event.created_at.desc())
            .limit(5)
        )
        recent_events = recent_events_result.scalars().all()
        
        # Add attendee count to each event
        for event in recent_events:
            event.attendee_count = len(event.attendees) if event.attendees else 0
        
        # Get event status counts
        status_counts_result = await session.execute(
            select(Event.status, func.count(Event.id))
            .group_by(Event.status)
        )
        status_counts = dict(status_counts_result.all())
        
        return templates.TemplateResponse(
            "admin/dashboard.html",
            {
                "request": request,
                "current_year": datetime.now().year,
                "stats": stats,
                "recent_events": recent_events,
                "status_counts": status_counts,
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load admin dashboard: {str(e)}"
        ) from e


# Attendee Templates
@router.get("/dashboard", response_class=HTMLResponse)
async def attendee_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """Attendee dashboard with personal statistics and events."""
    try:
        # Get user statistics
        user_stats = await get_user_dashboard_stats(session, current_user.id)
        
        # Get user's events
        my_events = await get_user_events(session, current_user.id)
        
        # Get recent matches
        recent_matches = await get_user_recent_matches(session, current_user.id, limit=5)
        
        # Calculate profile completion
        profile_completion = calculate_profile_completion(current_user)
        
        return templates.TemplateResponse(
            "attendee/dashboard.html",
            {
                "request": request,
                "current_year": datetime.now().year,
                "user_stats": user_stats,
                "my_events": my_events,
                "recent_matches": recent_matches,
                "profile_completion": profile_completion,
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load dashboard: {str(e)}"
        ) from e


# Public Templates
@router.get("/", response_class=HTMLResponse)
async def home_page(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Public home page."""
    try:
        # Get upcoming public events
        upcoming_events_result = await session.execute(
            select(Event)
            .where(
                Event.status == EventStatus.PUBLISHED,
                Event.start_time > datetime.now(UTC)
            )
            .order_by(Event.start_time)
            .limit(3)
        )
        upcoming_events = upcoming_events_result.scalars().all()
        
        # Check if super user setup is available
        super_user_setup_available = await super_user_manager.can_create_super_user(session)
        
        return templates.TemplateResponse(
            "public/home.html",
            {
                "request": request,
                "current_year": datetime.now().year,
                "upcoming_events": upcoming_events,
                "super_user_setup_available": super_user_setup_available,
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load home page: {str(e)}"
        ) from e


# Events Templates
@router.get("/events", response_class=HTMLResponse)
async def events_list(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    page: int = 1,
    limit: int = 12,
):
    """Public events listing page."""
    try:
        # Calculate offset
        offset = (page - 1) * limit
        
        # Get published events
        events_query = (
            select(Event)
            .where(Event.status == EventStatus.PUBLISHED)
            .order_by(Event.start_time)
            .offset(offset)
            .limit(limit)
        )
        events_result = await session.execute(events_query)
        events = events_result.scalars().all()
        
        # Get total count for pagination
        count_query = select(func.count(Event.id)).where(Event.status == EventStatus.PUBLISHED)
        count_result = await session.execute(count_query)
        total_count = count_result.scalar() or 0
        total_pages = (total_count + limit - 1) // limit
        
        # Add computed properties to events
        for event in events:
            # Add attendee count
            attendee_count_result = await session.execute(
                select(func.count(Attendee.id)).where(Attendee.event_id == event.id)
            )
            event.attendee_count = attendee_count_result.scalar() or 0
            
            # Determine if user can register
            event.can_register = (
                event.status == EventStatus.PUBLISHED and
                (not event.max_attendees or event.attendee_count < event.max_attendees) and
                event.start_time > datetime.now(UTC)
            )
            event.is_full = event.max_attendees and event.attendee_count >= event.max_attendees
        
        return templates.TemplateResponse(
            "events/list.html",
            {
                "request": request,
                "current_year": datetime.now().year,
                "events": events,
                "current_page": page,
                "total_pages": total_pages,
                "total_count": total_count,
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load events: {str(e)}"
        ) from e


# HTMX Partial Templates
@router.get("/admin/statistics/refresh")
async def refresh_admin_stats(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Refresh admin dashboard statistics via HTMX."""
    try:
        stats = await get_admin_dashboard_stats(session)
        return templates.TemplateResponse(
            "components/admin_stats.html",
            {"stats": stats}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh statistics: {str(e)}"
        ) from e


# Helper Functions
async def get_admin_dashboard_stats(session: AsyncSession) -> Dict[str, Any]:
    """Get statistics for admin dashboard."""
    # Total events
    total_events_result = await session.execute(
        select(func.count(Event.id))
    )
    total_events = total_events_result.scalar() or 0
    
    # Total attendees
    total_attendees_result = await session.execute(
        select(func.count(Attendee.id))
    )
    total_attendees = total_attendees_result.scalar() or 0
    
    # Active events
    active_events_result = await session.execute(
        select(func.count(Event.id)).where(Event.status == EventStatus.ACTIVE)
    )
    active_events = active_events_result.scalar() or 0
    
    # Total matches
    total_matches_result = await session.execute(
        select(func.count(Match.id))
    )
    total_matches = total_matches_result.scalar() or 0
    
    return {
        "total_events": total_events,
        "total_attendees": total_attendees,
        "active_events": active_events,
        "total_matches": total_matches,
    }


async def get_user_dashboard_stats(session: AsyncSession, user_id: uuid.UUID) -> Dict[str, Any]:
    """Get statistics for user dashboard."""
    # Events registered
    events_registered_result = await session.execute(
        select(func.count(Attendee.id)).where(Attendee.user_id == user_id)
    )
    events_registered = events_registered_result.scalar() or 0
    
    # Total matches for this user
    total_matches_result = await session.execute(
        select(func.count(Match.id))
        .join(Attendee, (Attendee.id == Match.attendee1_id) | (Attendee.id == Match.attendee2_id))
        .where(Attendee.user_id == user_id)
    )
    total_matches = total_matches_result.scalar() or 0
    
    # Mutual matches
    mutual_matches_result = await session.execute(
        select(func.count(Match.id))
        .join(Attendee, (Attendee.id == Match.attendee1_id) | (Attendee.id == Match.attendee2_id))
        .where(
            Attendee.user_id == user_id,
            Match.attendee1_response == MatchResponse.YES,
            Match.attendee2_response == MatchResponse.YES
        )
    )
    mutual_matches = mutual_matches_result.scalar() or 0
    
    return {
        "events_registered": events_registered,
        "total_matches": total_matches,
        "mutual_matches": mutual_matches,
    }


async def get_user_events(session: AsyncSession, user_id: uuid.UUID) -> list:
    """Get events for a user with registration status."""
    attendees_result = await session.execute(
        select(Attendee)
        .options(selectinload(Attendee.event))
        .where(Attendee.user_id == user_id)
        .order_by(Attendee.registered_at.desc())
    )
    attendees = attendees_result.scalars().all()
    
    events = []
    for attendee in attendees:
        event = attendee.event
        events.append({
            "id": event.id,
            "name": event.name,
            "location": event.location,
            "start_time": event.start_time,
            "status": event.status,
            "attendee_id": attendee.id,
            "registration_status": "confirmed" if attendee.registration_confirmed else "pending",
            "check_in_status": attendee.checked_in,
            "can_check_in": event.status == EventStatus.ACTIVE and not attendee.checked_in,
            "current_round": 1,  # TODO: Get actual current round
            "total_rounds": 5,   # TODO: Get actual total rounds
        })
    
    return events


async def get_user_recent_matches(session: AsyncSession, user_id: uuid.UUID, limit: int = 5) -> list:
    """Get recent matches for a user."""
    matches_result = await session.execute(
        select(Match)
        .join(Attendee, (Attendee.id == Match.attendee1_id) | (Attendee.id == Match.attendee2_id))
        .options(
            selectinload(Match.attendee1),
            selectinload(Match.attendee2),
            selectinload(Match.event)
        )
        .where(Attendee.user_id == user_id)
        .order_by(Match.created_at.desc())
        .limit(limit)
    )
    matches = matches_result.scalars().all()
    
    recent_matches = []
    for match in matches:
        # Determine which attendee is the current user
        user_attendee = None
        other_attendee = None
        
        if match.attendee1.user_id == user_id:
            user_attendee = match.attendee1
            other_attendee = match.attendee2
            my_response = match.attendee1_response
        else:
            user_attendee = match.attendee2
            other_attendee = match.attendee1
            my_response = match.attendee2_response
        
        recent_matches.append({
            "match_id": match.id,
            "event_name": match.event.name,
            "other_person_name": other_attendee.display_name,
            "my_response": my_response,
            "is_mutual": match.is_mutual_match,
            "created_at": match.created_at,
        })
    
    return recent_matches


def calculate_profile_completion(user: User) -> int:
    """Calculate profile completion percentage."""
    total_fields = 5
    completed_fields = 0
    
    if user.email:
        completed_fields += 1
    if hasattr(user, 'display_name') and user.display_name:
        completed_fields += 1
    # Add more profile field checks as needed
    
    return int((completed_fields / total_fields) * 100)