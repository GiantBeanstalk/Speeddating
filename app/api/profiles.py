"""
Public Profile API endpoints.

Handles public profile viewing, bio management, and QR code profile access.
"""
import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from app.database import get_async_session
from app.models import User, Attendee, Event, Match, MatchResponse
from app.auth import current_active_user, optional_current_user
from app.utils.content_filter import bio_filter, ContentFilterResult


router = APIRouter(prefix="/profiles", tags=["Profiles"])


# Pydantic models
class BioUpdateRequest(BaseModel):
    public_bio: str = Field(..., max_length=500)


class BioValidationResponse(BaseModel):
    is_valid: bool
    message: str
    suggestions: Optional[list[str]] = None
    guidelines: Optional[Dict[str, list[str]]] = None


class PublicProfileResponse(BaseModel):
    id: str
    display_name: str
    age: Optional[int]
    category: str
    public_bio: Optional[str]
    event_name: Optional[str]
    profile_visible: bool
    is_matched: bool = False
    contact_info: Optional[Dict[str, str]] = None
    message: Optional[str] = None


class ProfileQRResponse(BaseModel):
    profile_url: str
    qr_token: str
    expires_in_hours: int = 72


@router.get("/validate-bio")
async def validate_bio_content(
    bio: str = Query(..., max_length=500, description="Bio content to validate")
):
    """Validate bio content for filtering violations."""
    
    filter_result = bio_filter.filter_bio(bio)
    
    response = BioValidationResponse(
        is_valid=filter_result.is_valid,
        message=filter_result.violation_message if not filter_result.is_valid else "Bio content is valid"
    )
    
    if not filter_result.is_valid:
        response.suggestions = bio_filter.get_safe_bio_suggestions()
        response.guidelines = bio_filter.get_bio_guidelines()
    
    return response


@router.put("/bio")
async def update_bio(
    bio_request: BioUpdateRequest,
    attendee_id: uuid.UUID = Query(..., description="Attendee ID to update bio for"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user)
):
    """Update public bio for an attendee profile."""
    
    # Get attendee
    attendee_result = await session.execute(
        select(Attendee)
        .options(selectinload(Attendee.event))
        .where(Attendee.id == attendee_id)
    )
    attendee = attendee_result.scalar_one_or_none()
    
    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendee profile not found"
        )
    
    # Check authorization (only the attendee or event organizer can update)
    if attendee.user_id != current_user.id and attendee.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile"
        )
    
    # Validate and set bio
    success, message = attendee.validate_and_set_public_bio(bio_request.public_bio)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    await session.commit()
    
    return {
        "message": "Bio updated successfully",
        "bio": attendee.public_bio
    }


@router.get("/{attendee_id}", response_model=PublicProfileResponse)
async def get_public_profile(
    attendee_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: Optional[User] = Depends(optional_current_user)
):
    """Get public profile for an attendee."""
    
    # Get attendee with related data
    attendee_result = await session.execute(
        select(Attendee)
        .options(
            selectinload(Attendee.event),
            selectinload(Attendee.user)
        )
        .where(Attendee.id == attendee_id)
    )
    attendee = attendee_result.scalar_one_or_none()
    
    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    # Check if user is admin or has match
    is_admin = current_user and (
        current_user.is_organizer or 
        current_user.is_superuser or
        attendee.event.organizer_id == current_user.id
    )
    
    is_matched = False
    if current_user:
        # Check if current user has a mutual match with this attendee
        match_result = await session.execute(
            select(Match)
            .join(Attendee, 
                  (Match.attendee1_id == Attendee.id) | (Match.attendee2_id == Attendee.id))
            .where(
                Attendee.user_id == current_user.id,
                (
                    (Match.attendee1_id == attendee_id) | 
                    (Match.attendee2_id == attendee_id)
                ),
                Match.attendee1_response == MatchResponse.YES,
                Match.attendee2_response == MatchResponse.YES
            )
        )
        mutual_match = match_result.scalar_one_or_none()
        is_matched = mutual_match is not None
    
    # Get profile data with appropriate privacy controls
    profile_data = attendee.get_public_profile_data(
        requester_is_admin=is_admin,
        is_matched=is_matched
    )
    
    # Convert to response format
    response = PublicProfileResponse(
        id=profile_data["id"],
        display_name=profile_data["display_name"],
        age=profile_data.get("age"),
        category=profile_data["category"],
        public_bio=profile_data.get("public_bio"),
        event_name=profile_data.get("event_name"),
        profile_visible=profile_data["profile_visible"],
        is_matched=is_matched
    )
    
    # Add contact info if available
    if "contact_info" in profile_data:
        response.contact_info = profile_data["contact_info"]
    
    # Add message if profile is private
    if not profile_data["profile_visible"]:
        response.message = profile_data.get("message", "This profile is private")
    
    return response


@router.get("/{attendee_id}/qr-token")
async def generate_profile_qr_token(
    attendee_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user)
):
    """Generate QR token for profile viewing (attendee or organizer only)."""
    
    # Get attendee
    attendee_result = await session.execute(
        select(Attendee)
        .options(selectinload(Attendee.event))
        .where(Attendee.id == attendee_id)
    )
    attendee = attendee_result.scalar_one_or_none()
    
    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendee not found"
        )
    
    # Check authorization
    if attendee.user_id != current_user.id and attendee.event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to generate QR token for this profile"
        )
    
    # Generate profile QR token
    from app.models.qr_login import QRLogin
    
    # Revoke any existing profile QR tokens
    existing_tokens = await session.execute(
        select(QRLogin).where(
            QRLogin.attendee_id == attendee_id,
            QRLogin.token_type == "profile_view",
            QRLogin.is_active == True
        )
    )
    
    for token in existing_tokens.scalars():
        token.revoke_token("Replaced with new token")
    
    # Create new token
    qr_login = QRLogin.create_for_attendee(
        attendee_id=attendee_id,
        event_id=attendee.event_id,
        user_id=attendee.user_id,
        expire_hours=72,  # 3 days for profile viewing
        token_type="profile_view"
    )
    
    # Set QR URL for profile viewing
    from app.config import settings
    base_url = settings.get("qr_code_base_url", "http://localhost:8000")
    qr_login.qr_code_url = f"{base_url}/profiles/{attendee_id}?qr_token={qr_login.token}"
    
    session.add(qr_login)
    await session.commit()
    
    return ProfileQRResponse(
        profile_url=qr_login.qr_code_url,
        qr_token=qr_login.token,
        expires_in_hours=72
    )


@router.get("/{attendee_id}/qr-access")
async def access_profile_via_qr(
    attendee_id: uuid.UUID,
    qr_token: str = Query(..., description="QR token for profile access"),
    session: AsyncSession = Depends(get_async_session)
):
    """Access profile via QR token (no authentication required)."""
    
    # Validate QR token
    from app.services.qr_service import QRCodeService
    qr_service = QRCodeService(session)
    
    # Get attendee first to get event_id
    attendee_result = await session.execute(
        select(Attendee).where(Attendee.id == attendee_id)
    )
    attendee = attendee_result.scalar_one_or_none()
    
    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    # Validate token
    validation_result = await qr_service.validate_qr_token(
        token=qr_token,
        event_id=attendee.event_id
    )
    
    if not validation_result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired QR token"
        )
    
    # Check if token is for this specific attendee and is a profile view token
    qr_login = validation_result["qr_login"]
    if (qr_login.attendee_id != attendee_id or 
        qr_login.token_type != "profile_view"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="QR token is not valid for this profile"
        )
    
    # Return public profile data (no contact info unless mutual match)
    profile_data = attendee.get_public_profile_data(
        requester_is_admin=False,
        is_matched=False
    )
    
    return PublicProfileResponse(
        id=profile_data["id"],
        display_name=profile_data["display_name"],
        age=profile_data.get("age"),
        category=profile_data["category"],
        public_bio=profile_data.get("public_bio"),
        event_name=profile_data.get("event_name"),
        profile_visible=profile_data["profile_visible"],
        is_matched=False,
        message="Accessed via QR code"
    )


@router.put("/{attendee_id}/visibility")
async def update_profile_visibility(
    attendee_id: uuid.UUID,
    visible: bool = Query(..., description="Whether profile should be visible"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user)
):
    """Update profile visibility settings."""
    
    # Get attendee
    attendee_result = await session.execute(
        select(Attendee).where(Attendee.id == attendee_id)
    )
    attendee = attendee_result.scalar_one_or_none()
    
    if not attendee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendee not found"
        )
    
    # Check authorization
    if attendee.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile"
        )
    
    attendee.profile_visible = visible
    await session.commit()
    
    return {
        "message": f"Profile {'enabled' if visible else 'disabled'} successfully",
        "profile_visible": visible
    }


@router.get("/bio-guidelines")
async def get_bio_guidelines():
    """Get guidelines for writing appropriate bio content."""
    
    return {
        "guidelines": bio_filter.get_bio_guidelines(),
        "suggestions": bio_filter.get_safe_bio_suggestions(),
        "max_length": 500
    }