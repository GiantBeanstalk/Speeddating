"""
Password Reset API endpoints.

Provides REST API endpoints for password reset functionality
with HTML form integration and security validation.
"""

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.security import sanitize_email, validate_csrf_token
from app.services.password_reset import PasswordResetService

router = APIRouter(tags=["password-reset"])


class ForgotPasswordRequest(BaseModel):
    """Request model for forgot password."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request model for password reset."""

    password: str
    confirm_password: str


@router.post("/forgot-password")
async def request_password_reset(
    request: Request,
    email: str = Form(...),
    csrf_token: str = Form(...),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Request a password reset email.

    This endpoint processes forgot password requests from the HTML form.
    It validates the email and sends a password reset link.
    """
    try:
        # Validate CSRF token
        session_id = request.session.get("session_id", "anonymous")

        if not validate_csrf_token(csrf_token, session_id):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": "Invalid security token. Please refresh the page and try again.",
                },
            )

        # Sanitize email input
        try:
            clean_email = sanitize_email(email)
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": f"Invalid email address: {str(e)}",
                },
            )

        # Create password reset service
        reset_service = PasswordResetService(session)

        # Get base URL for reset links
        base_url = str(request.base_url).rstrip("/")

        # Process reset request
        await reset_service.request_password_reset(clean_email, base_url)

        # Always return success for security (don't reveal if email exists)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "If an account with that email exists, we've sent password reset instructions.",
            },
        )

    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code, content={"success": False, "message": e.detail}
        )
    except Exception as e:
        print(f"Unexpected error in password reset request: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "An unexpected error occurred. Please try again later.",
            },
        )


@router.post("/reset-password/{token}")
async def reset_password(
    token: str,
    request: Request,
    password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(...),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Reset password using a valid reset token.

    This endpoint processes password reset from the HTML form.
    It validates the token and updates the user's password.
    """
    try:
        # Validate CSRF token
        session_id = request.session.get("session_id", "anonymous")

        if not validate_csrf_token(csrf_token, session_id):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": "Invalid security token. Please refresh the page and try again.",
                },
            )

        # Validate password confirmation
        if password != confirm_password:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "Passwords do not match."},
            )

        # Validate password strength (basic checks)
        if len(password) < 8:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": "Password must be at least 8 characters long.",
                },
            )

        if len(password) > 128:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": "Password must be less than 128 characters long.",
                },
            )

        # Get client info for logging
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")

        # Create password reset service
        reset_service = PasswordResetService(session)

        # Reset password
        success = await reset_service.reset_password(
            token=token,
            new_password=password,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "success": True,
                    "message": "Your password has been reset successfully. You can now log in with your new password.",
                },
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "message": "Failed to reset password. Please try again.",
                },
            )

    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code, content={"success": False, "message": e.detail}
        )
    except Exception as e:
        print(f"Unexpected error in password reset: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "An unexpected error occurred. Please try again later.",
            },
        )


@router.get("/reset-password/{token}/validate")
async def validate_reset_token(
    token: str, session: AsyncSession = Depends(get_async_session)
):
    """
    Validate a password reset token.

    This endpoint checks if a reset token is valid and not expired.
    Used by the frontend to determine if the reset form should be shown.
    """
    try:
        # Create password reset service
        reset_service = PasswordResetService(session)

        # Validate token
        reset_token = await reset_service.validate_reset_token(token)

        if reset_token:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "valid": True,
                    "user_email": reset_token.user.email,
                    "expires_at": reset_token.expires_at.isoformat(),
                },
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"valid": False, "message": "Invalid or expired reset token."},
            )

    except Exception as e:
        print(f"Error validating reset token: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"valid": False, "message": "Failed to validate reset token."},
        )


# API endpoints for JSON-based requests (optional for API clients)
@router.post("/api/forgot-password", response_model=dict)
async def api_request_password_reset(
    request_data: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """
    API endpoint for requesting password reset (JSON).

    This is for API clients that want to use JSON instead of form data.
    """
    try:
        # Sanitize email input
        try:
            clean_email = sanitize_email(request_data.email)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid email address: {str(e)}",
            ) from e

        # Create password reset service
        reset_service = PasswordResetService(session)

        # Get base URL for reset links
        base_url = str(request.base_url).rstrip("/")

        # Process reset request
        await reset_service.request_password_reset(clean_email, base_url)

        # Always return success for security
        return {
            "message": "If an account with that email exists, we've sent password reset instructions."
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in API password reset request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
        ) from e


@router.post("/api/reset-password/{token}", response_model=dict)
async def api_reset_password(
    token: str,
    request_data: ResetPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """
    API endpoint for resetting password (JSON).

    This is for API clients that want to use JSON instead of form data.
    """
    try:
        # Validate password confirmation
        if request_data.password != request_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match.",
            )

        # Validate password strength
        if len(request_data.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long.",
            )

        if len(request_data.password) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be less than 128 characters long.",
            )

        # Get client info for logging
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")

        # Create password reset service
        reset_service = PasswordResetService(session)

        # Reset password
        success = await reset_service.reset_password(
            token=token,
            new_password=request_data.password,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if success:
            return {
                "message": "Your password has been reset successfully. You can now log in with your new password."
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to reset password. Please try again.",
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in API password reset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
        ) from e
