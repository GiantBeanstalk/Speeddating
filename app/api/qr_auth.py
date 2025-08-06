"""
QR Code Authentication API endpoints.

Handles QR code generation, validation, and fast login functionality.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_active_organizer, current_active_user
from app.database import get_async_session
from app.models import User
from app.services import create_pdf_service, create_qr_service

router = APIRouter(prefix="/qr", tags=["QR Authentication"])


# Pydantic models for requests/responses
class QRTokenRequest(BaseModel):
    attendee_id: uuid.UUID
    expire_hours: int = 24
    max_uses: int = 10


class QRTokenResponse(BaseModel):
    token_id: uuid.UUID
    qr_url: str
    expires_at: str
    max_uses: int
    attendee_name: str


class QRLoginRequest(BaseModel):
    token: str


class QRLoginResponse(BaseModel):
    success: bool
    user_id: uuid.UUID | None = None
    attendee_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None
    remaining_uses: int | None = None
    message: str


class QRValidationResponse(BaseModel):
    valid: bool
    attendee_name: str | None = None
    event_name: str | None = None
    expires_at: str | None = None
    remaining_uses: int | None = None


@router.post("/generate-token", response_model=QRTokenResponse)
async def generate_qr_token(
    request: QRTokenRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Generate a QR token for an attendee (organizer only)."""

    qr_service = await create_qr_service(session)

    try:
        qr_login = await qr_service.generate_attendee_qr_token(
            attendee_id=request.attendee_id,
            expire_hours=request.expire_hours,
            max_uses=request.max_uses,
        )

        # Get attendee info for response
        attendee = qr_login.attendee

        return QRTokenResponse(
            token_id=qr_login.id,
            qr_url=qr_login.qr_code_url,
            expires_at=qr_login.expires_at.isoformat(),
            max_uses=qr_login.max_uses,
            attendee_name=attendee.display_name,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate QR token",
        ) from e


@router.get("/validate/{event_id}")
async def validate_qr_token(
    event_id: uuid.UUID, token: str, session: AsyncSession = Depends(get_async_session)
):
    """Validate a QR token without using it."""

    qr_service = await create_qr_service(session)

    try:
        # Use the validation method from QRCodeService
        validation_result = await qr_service.validate_qr_token(
            token=token,
            event_id=event_id,
            ip_address=None,  # Don't track IP for validation
            user_agent=None,  # Don't track user agent for validation
        )

        if validation_result:
            attendee = validation_result["attendee"]
            event = validation_result["event"]
            remaining_uses = validation_result["remaining_uses"]

            return QRValidationResponse(
                valid=True,
                attendee_name=attendee.display_name,
                event_name=event.name,
                expires_at=validation_result["qr_login"].expires_at.isoformat(),
                remaining_uses=remaining_uses,
            )
        else:
            return QRValidationResponse(valid=False)

    except Exception:
        return QRValidationResponse(valid=False)


@router.post("/login/{event_id}", response_model=QRLoginResponse)
async def qr_fast_login(
    event_id: uuid.UUID,
    request: QRLoginRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Perform fast login using QR token."""

    qr_service = await create_qr_service(session)

    # Get client information
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    try:
        validation_result = await qr_service.validate_qr_token(
            token=request.token,
            event_id=event_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if validation_result:
            attendee = validation_result["attendee"]
            user = validation_result["user"]
            remaining_uses = validation_result["remaining_uses"]

            # Here you would typically create a session or JWT token
            # For now, we just return the user information

            return QRLoginResponse(
                success=True,
                user_id=user.id,
                attendee_id=attendee.id,
                event_id=event_id,
                remaining_uses=remaining_uses,
                message=f"Welcome {attendee.display_name}!",
            )
        else:
            return QRLoginResponse(success=False, message="Invalid or expired QR token")

    except Exception:
        return QRLoginResponse(success=False, message="Authentication failed")


@router.get("/image/{attendee_id}")
async def get_qr_code_image(
    attendee_id: uuid.UUID,
    size: int = 10,
    border: int = 4,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """Get QR code image for an attendee."""

    qr_service = await create_qr_service(session)

    try:
        # Get or generate QR token for attendee
        qr_login = await qr_service.generate_attendee_qr_token(attendee_id)

        # Generate QR code image
        qr_image = qr_service.create_qr_code_image(
            qr_login.qr_code_url, size=size, border=border
        )

        return StreamingResponse(
            qr_image,
            media_type="image/png",
            headers={
                "Content-Disposition": f"inline; filename=qr_code_{attendee_id}.png"
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate QR code image",
        ) from e


@router.get("/badge/{attendee_id}")
async def get_attendee_badge(
    attendee_id: uuid.UUID,
    include_qr: bool = True,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_user),
):
    """Generate PDF badge for a single attendee."""

    pdf_service = await create_pdf_service(session)

    try:
        pdf_badge = await pdf_service.generate_single_badge(
            attendee_id=attendee_id, include_qr=include_qr
        )

        return StreamingResponse(
            pdf_badge,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=badge_{attendee_id}.pdf"
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate badge",
        ) from e


@router.get("/badges/event/{event_id}")
async def get_event_badges(
    event_id: uuid.UUID,
    include_qr: bool = True,
    font_size: int = 8,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Generate PDF badges for all attendees of an event (organizer only)."""

    pdf_service = await create_pdf_service(session)

    try:
        pdf_badges = await pdf_service.generate_event_badges(
            event_id=event_id, include_qr=include_qr, font_size=font_size
        )

        return StreamingResponse(
            pdf_badges,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=event_badges_{event_id}.pdf"
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate event badges",
        ) from e


@router.delete("/revoke/{attendee_id}")
async def revoke_qr_token(
    attendee_id: uuid.UUID,
    reason: str = "Manually revoked",
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Revoke QR token for an attendee (organizer only)."""

    qr_service = await create_qr_service(session)

    try:
        success = await qr_service.revoke_attendee_qr_token(
            attendee_id=attendee_id, reason=reason
        )

        if success:
            return {"message": "QR token revoked successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active QR token found for attendee",
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke QR token",
        ) from e


@router.put("/extend/{attendee_id}")
async def extend_qr_token(
    attendee_id: uuid.UUID,
    additional_hours: int = 24,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Extend QR token expiry for an attendee (organizer only)."""

    qr_service = await create_qr_service(session)

    try:
        qr_login = await qr_service.extend_qr_token_expiry(
            attendee_id=attendee_id, additional_hours=additional_hours
        )

        if qr_login:
            return {
                "message": "QR token extended successfully",
                "new_expiry": qr_login.expires_at.isoformat(),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active QR token found for attendee",
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extend QR token",
        ) from e


@router.get("/stats/{event_id}")
async def get_qr_stats(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Get QR token statistics for an event (organizer only)."""

    qr_service = await create_qr_service(session)

    try:
        stats = await qr_service.get_qr_token_stats(event_id)
        return stats

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve QR statistics",
        ) from e


@router.post("/cleanup")
async def cleanup_expired_tokens(
    event_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(current_active_organizer),
):
    """Clean up expired QR tokens (organizer only)."""

    qr_service = await create_qr_service(session)

    try:
        cleaned_count = await qr_service.cleanup_expired_tokens(event_id)

        return {
            "message": f"Cleaned up {cleaned_count} expired tokens",
            "cleaned_count": cleaned_count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup expired tokens",
        ) from e
