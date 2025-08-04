"""
API package for all HTTP endpoints.
"""

from .qr_auth import router as qr_auth_router
from .events import router as events_router
from .attendees import router as attendees_router

__all__ = [
    "qr_auth_router",
    "events_router", 
    "attendees_router"
]