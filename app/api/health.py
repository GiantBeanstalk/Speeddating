"""
Health check and system status endpoints.

Provides endpoints for monitoring application health, configuration status,
and system diagnostics.
"""

from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.auth import current_superuser
from app.models.user import User
from app.utils.settings_validator import validate_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns basic application status without sensitive information.
    Available to all users without authentication.
    """
    return {
        "status": "healthy",
        "service": "Speed Dating Application",
        "version": "1.0.0"
    }


@router.get("/health/detailed")
async def detailed_health_check(
    current_user: User = Depends(current_superuser)
) -> Dict[str, Any]:
    """
    Detailed health check with configuration validation.
    
    Returns comprehensive system status including configuration validation.
    Requires superuser privileges.
    """
    try:
        # Validate settings
        validation_report = validate_settings()
        
        # Basic system info
        system_info = {
            "status": "healthy" if validation_report["valid"] else "degraded",
            "service": "Speed Dating Application",
            "version": "1.0.0",
            "configuration": {
                "valid": validation_report["valid"],
                "errors_count": len(validation_report["errors"]),
                "warnings_count": len(validation_report["warnings"]),
                "checks_passed": len(validation_report["info"])
            }
        }
        
        # Add validation details if there are issues
        if validation_report["errors"] or validation_report["warnings"]:
            system_info["validation_details"] = {
                "errors": validation_report["errors"],
                "warnings": validation_report["warnings"],
                "summary": validation_report["summary"]
            }
        
        # Set appropriate status code
        status_code = status.HTTP_200_OK if validation_report["valid"] else status.HTTP_503_SERVICE_UNAVAILABLE
        
        return JSONResponse(
            status_code=status_code,
            content=system_info
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/health/settings")
async def settings_validation_check(
    current_user: User = Depends(current_superuser)
) -> Dict[str, Any]:
    """
    Comprehensive settings validation endpoint.
    
    Returns detailed configuration validation report.
    Requires superuser privileges.
    """
    try:
        validation_report = validate_settings()
        
        return JSONResponse(
            status_code=status.HTTP_200_OK if validation_report["valid"] else status.HTTP_400_BAD_REQUEST,
            content=validation_report
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Settings validation failed: {str(e)}"
        )


@router.post("/health/settings/validate")
async def trigger_settings_validation(
    current_user: User = Depends(current_superuser)
) -> Dict[str, Any]:
    """
    Trigger a fresh settings validation.
    
    Forces a complete re-validation of all settings and returns the report.
    Requires superuser privileges.
    """
    try:
        # Force fresh validation
        from app.utils.settings_validator import SettingsHealthCheck
        
        checker = SettingsHealthCheck()
        validation_report = checker.validate_all()
        
        return {
            "message": "Settings validation completed",
            "triggered_at": str(checker),
            "report": validation_report
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger settings validation: {str(e)}"
        )