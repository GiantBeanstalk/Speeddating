"""
Page Object Model classes for Playwright E2E testing.

This module provides page objects that encapsulate the interactions
with different pages of the Speed Dating application.
"""

from .auth_pages import LoginPage, RegisterPage, ForgotPasswordPage, ResetPasswordPage
from .admin_pages import AdminDashboardPage, EventManagementPage, AttendeeManagementPage
from .attendee_pages import AttendeeDashboardPage, MatchingPage, ProfilePage
from .public_pages import HomePage, EventListPage, PublicProfilePage

__all__ = [
    "LoginPage",
    "RegisterPage", 
    "ForgotPasswordPage",
    "ResetPasswordPage",
    "AdminDashboardPage",
    "EventManagementPage",
    "AttendeeManagementPage",
    "AttendeeDashboardPage",
    "MatchingPage", 
    "ProfilePage",
    "HomePage",
    "EventListPage",
    "PublicProfilePage",
]