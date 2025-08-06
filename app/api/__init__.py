"""
API package for all HTTP endpoints.
"""

from .attendees import router as attendees_router
from .events import router as events_router
from .profiles import router as profiles_router
from .qr_auth import router as qr_auth_router
from .rounds import router as rounds_router

__all__ = [
    "qr_auth_router",
    "events_router",
    "attendees_router",
    "rounds_router",
    "profiles_router",
]
