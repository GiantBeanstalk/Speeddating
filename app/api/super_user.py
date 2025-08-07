"""
Super User Registration API endpoints.

Provides secure one-time super user account creation functionality.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_user_manager
from app.database import get_async_session
from app.models import User
from app.security import super_user_manager
from app.schemas import UserCreate

router = APIRouter(prefix="/setup", tags=["Super User Setup"])

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="app/templates")


# Pydantic models
class SuperUserCreateRequest(BaseModel):
    """Request model for super user creation."""
    secret_key: str = Field(..., min_length=20, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)


class SuperUserCreateResponse(BaseModel):
    """Response model for super user creation."""
    success: bool
    message: str
    user_id: str | None = None


class SuperUserStatusResponse(BaseModel):
    """Response model for super user setup status."""
    setup_available: bool
    super_user_exists: bool
    secret_key_exists: bool
    message: str


@router.get("/super-user", response_class=HTMLResponse)
async def super_user_setup_page(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Display the super user setup page if available."""
    try:
        # Check if setup is available
        can_create = await super_user_manager.can_create_super_user(session)
        super_user_exists = await super_user_manager.super_user_exists(session)
        
        if not can_create:
            if super_user_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Super user already exists. Setup is no longer available."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Super user setup is not available. Secret key not found."
                )
        
        return templates.TemplateResponse(
            "setup/super_user.html",
            {
                "request": request,
                "title": "Super User Setup",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load super user setup: {str(e)}"
        ) from e


@router.get("/super-user/status")
async def get_super_user_status(
    session: AsyncSession = Depends(get_async_session),
) -> SuperUserStatusResponse:
    """Check if super user setup is available."""
    try:
        super_user_exists = await super_user_manager.super_user_exists(session)
        secret_key_exists = super_user_manager.secret_key_exists()
        can_create = await super_user_manager.can_create_super_user(session)
        
        if super_user_exists:
            message = "Super user already exists. Setup is disabled."
        elif not secret_key_exists:
            message = "Secret key not found. Setup is not available."
        elif can_create:
            message = "Super user setup is available."
        else:
            message = "Super user setup is not available."
        
        return SuperUserStatusResponse(
            setup_available=can_create,
            super_user_exists=super_user_exists,
            secret_key_exists=secret_key_exists,
            message=message,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check super user status: {str(e)}"
        ) from e


@router.post("/super-user")
async def create_super_user(
    data: SuperUserCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user_manager = Depends(get_user_manager),
) -> SuperUserCreateResponse:
    """Create the first super user account."""
    try:
        # Check if super user creation is allowed
        can_create = await super_user_manager.can_create_super_user(session)
        if not can_create:
            super_user_exists = await super_user_manager.super_user_exists(session)
            if super_user_exists:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Super user already exists. Registration is disabled."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Super user setup is not available. Secret key not found."
                )
        
        # Verify the secret key
        if not super_user_manager.verify_secret_key(data.secret_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid secret key provided."
            )
        
        # Create the user with super user privileges
        user_create = UserCreate(
            email=data.email,
            password=data.password,
            is_active=True,
            is_superuser=True,
            is_verified=True,
            first_name=data.first_name,
            last_name=data.last_name,
            display_name=data.display_name,
        )
        
        # Create the user using FastAPI Users manager
        user = await user_manager.create(user_create, safe=False)
        
        # Delete the secret key file after successful creation
        super_user_manager.delete_secret_key()
        
        return SuperUserCreateResponse(
            success=True,
            message="Super user account created successfully. Setup is now disabled.",
            user_id=str(user.id),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create super user: {str(e)}"
        ) from e