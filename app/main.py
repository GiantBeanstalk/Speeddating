"""
Main FastAPI application entry point.

This module creates and configures the FastAPI application with all routes,
middleware, and startup/shutdown event handlers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    attendees_router,
    events_router,
    match_results_router,
    profiles_router,
    qr_auth_router,
    rounds_router,
)
from app.api.health import router as health_router
from app.api.password_reset import router as password_reset_router
from app.api.super_user import router as super_user_router
from app.api.templates import router as templates_router
from app.api.websockets import router as websockets_router
from app.auth import (
    auth_router,
    register_router,
    reset_password_router,
    users_router,
    verify_router,
)
from app.config import settings
from app.database import close_db, create_db_and_tables
from app.logging_config import get_logger, setup_logging
from app.middleware import SecurityMiddleware
from app.middleware.error_handler import ErrorHandlingMiddleware
from app.security.super_user import initialize_super_user_secret
from app.utils.settings_validator import validate_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Initialize logging first
    setup_logging()
    logger = get_logger("startup")

    # Startup validation
    logger.info("Starting Speed Dating Application", extra={"operation": "startup"})
    print("🚀 Starting Speed Dating Application...")

    # Validate settings before startup
    validation_report = validate_settings()
    if not validation_report["valid"]:
        logger.error(
            "Configuration validation failed",
            extra={"operation": "startup", "errors": validation_report["errors"]},
        )
        print("❌ Configuration validation failed!")
        for error in validation_report["errors"]:
            print(f"   ERROR: {error}")
        raise RuntimeError("Invalid configuration - check settings and try again")

    if validation_report["warnings"]:
        logger.warning(
            "Configuration warnings detected",
            extra={"operation": "startup", "warnings": validation_report["warnings"]},
        )
        print("⚠️  Configuration warnings:")
        for warning in validation_report["warnings"]:
            print(f"   WARNING: {warning}")

    logger.info("Configuration validation passed", extra={"operation": "startup"})
    print("✅ Configuration validation passed")

    # Create database tables
    logger.info("Creating database tables", extra={"operation": "startup"})
    await create_db_and_tables()

    # Initialize super user secret on first run
    logger.info("Initializing super user secret", extra={"operation": "startup"})
    await initialize_super_user_secret()

    logger.info("Application startup complete", extra={"operation": "startup"})
    print("🎉 Application startup complete!")

    yield

    # Shutdown
    logger.info("Starting application shutdown", extra={"operation": "shutdown"})
    print("🛑 Shutting down application...")
    await close_db()
    logger.info("Application shutdown complete", extra={"operation": "shutdown"})
    print("👋 Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Speed Dating Application",
    description="A comprehensive speed dating event management system with OAuth2 authentication, QR code fast login, and category-based matching.",
    version="1.0.0",
    docs_url="/docs" if settings.get("DEBUG", False) else None,
    redoc_url="/redoc" if settings.get("DEBUG", False) else None,
    lifespan=lifespan,
)

# Error handling middleware (first - catches all errors)
app.add_middleware(ErrorHandlingMiddleware)

# Security middleware (second - processes all requests)
app.add_middleware(
    SecurityMiddleware,
    enable_sanitization=True,
    enable_rate_limiting=True,
    enable_security_headers=True,
    log_suspicious_activity=True,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get("ALLOWED_ORIGINS", ["http://localhost:3000"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Authentication routes
app.include_router(auth_router, prefix="/auth/jwt", tags=["auth"])
app.include_router(register_router, prefix="/auth", tags=["auth"])
app.include_router(reset_password_router, prefix="/auth", tags=["auth"])
app.include_router(verify_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])

# Password reset routes
app.include_router(password_reset_router, prefix="/auth", tags=["password-reset"])

# Health check routes
app.include_router(health_router, prefix="/api", tags=["health"])

# API routes
app.include_router(qr_auth_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(attendees_router, prefix="/api")
app.include_router(rounds_router, prefix="/api")
app.include_router(profiles_router, prefix="/api")
app.include_router(match_results_router, prefix="/api")

# WebSocket routes
app.include_router(websockets_router, tags=["websockets"])

# Template routes (HTML interface)
app.include_router(templates_router, tags=["templates"])

# Super user setup routes
app.include_router(super_user_router, tags=["setup"])


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Speed Dating Application",
        "version": "1.0.0",
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with basic information."""
    return {
        "message": "Welcome to the Speed Dating Application",
        "docs": "/docs"
        if settings.get("DEBUG", False)
        else "Documentation disabled in production",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.get("HOST", "127.0.0.1"),
        port=settings.get("PORT", 8000),
        reload=settings.get("DEBUG", False),
        log_level="info",
    )
