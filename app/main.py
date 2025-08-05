"""
Main FastAPI application entry point.

This module creates and configures the FastAPI application with all routes,
middleware, and startup/shutdown event handlers.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_db_and_tables, close_db
from app.auth import (
    auth_router, register_router, reset_password_router, 
    verify_router, users_router
)
from app.api import qr_auth_router, events_router, attendees_router, rounds_router, profiles_router
from app.api.websockets import router as websockets_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await create_db_and_tables()
    yield
    # Shutdown
    await close_db()


# Create FastAPI application
app = FastAPI(
    title="Speed Dating Application",
    description="A comprehensive speed dating event management system with OAuth2 authentication, QR code fast login, and category-based matching.",
    version="1.0.0",
    docs_url="/docs" if settings.get("DEBUG", False) else None,
    redoc_url="/redoc" if settings.get("DEBUG", False) else None,
    lifespan=lifespan
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

# API routes
app.include_router(qr_auth_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(attendees_router, prefix="/api")
app.include_router(rounds_router, prefix="/api")
app.include_router(profiles_router, prefix="/api")

# WebSocket routes
app.include_router(websockets_router, tags=["websockets"])

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Speed Dating Application",
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with basic information."""
    return {
        "message": "Welcome to the Speed Dating Application",
        "docs": "/docs" if settings.get("DEBUG", False) else "Documentation disabled in production",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.get("HOST", "127.0.0.1"),
        port=settings.get("PORT", 8000),
        reload=settings.get("DEBUG", False),
        log_level="info"
    )