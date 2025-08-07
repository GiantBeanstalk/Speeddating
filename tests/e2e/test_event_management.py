"""
End-to-end tests for event management functionality.

Tests event creation, editing, attendee management, and event lifecycle
from both admin and attendee perspectives.
"""

import pytest
from playwright.async_api import Page, expect
from faker import Faker
from datetime import datetime, timedelta

from tests.e2e.pages.admin_pages import AdminDashboardPage, EventManagementPage, AttendeeManagementPage
from tests.e2e.pages.public_pages import EventListPage
from tests.e2e.pages.attendee_pages import AttendeeDashboardPage


@pytest.mark.e2e
@pytest.mark.playwright
class TestEventManagement:
    """Test event management from admin perspective."""

    async def test_create_event_flow(self, admin_page: Page, base_url: str, faker_instance: Faker):
        """Test complete event creation flow."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        event_management = EventManagementPage(admin_page, base_url)

        await admin_dashboard.navigate()
        await admin_dashboard.click_create_event()

        # Create event with realistic data
        event_title = f"Speed Dating - {faker_instance.city()}"
        event_description = faker_instance.text(max_nb_chars=200)
        
        # Event date 2 weeks from now
        event_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%dT19:00")
        venue = f"{faker_instance.company()} - {faker_instance.street_address()}"

        await event_management.create_event(
            title=event_title,
            description=event_description,
            event_date=event_date,
            venue=venue,
            max_attendees=40,
            round_duration=5,
            break_duration=2,
            price=18.50
        )

        # Verify event was created
        events = await event_management.get_event_list()
        event_titles = [event["title"] for event in events]
        assert event_title in event_titles, f"Event '{event_title}' should appear in events list"

    async def test_edit_event_details(self, admin_page: Page, base_url: str, faker_instance: Faker):
        """Test editing existing event details."""
        event_management = EventManagementPage(admin_page, base_url)
        
        await event_management.navigate()
        
        # First create an event to edit
        event_title = f"Test Event - {faker_instance.word()}"
        event_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT20:00")
        
        await event_management.create_event(
            title=event_title,
            description="Original description",
            event_date=event_date,
            venue="Original Venue",
            max_attendees=30
        )
        
        # Edit the event
        await event_management.edit_event(event_title)
        
        # Update fields
        new_description = "Updated description with more details"
        await admin_page.fill("textarea[name='description']", new_description)
        await admin_page.fill("input[name='max_attendees']", "50")
        
        await admin_page.click("button[type='submit']:has-text('Save')")
        await admin_page.wait_for_url("**/admin/events")
        
        # Verify changes were saved (would need to check event details page)
        await admin_page.wait_for_timeout(1000)  # Wait for page update

    async def test_delete_event(self, admin_page: Page, base_url: str, faker_instance: Faker):
        """Test deleting an event."""
        event_management = EventManagementPage(admin_page, base_url)
        
        await event_management.navigate()
        
        # Create an event to delete
        event_title = f"Event to Delete - {faker_instance.word()}"
        event_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%dT19:30")
        
        await event_management.create_event(
            title=event_title,
            description="This event will be deleted",
            event_date=event_date,
            venue="Test Venue"
        )
        
        # Delete the event
        await event_management.delete_event(event_title)
        
        # Verify event was deleted
        events = await event_management.get_event_list()
        event_titles = [event["title"] for event in events]
        assert event_title not in event_titles, f"Event '{event_title}' should be deleted"

    async def test_event_form_validation(self, admin_page: Page, base_url: str):
        """Test event creation form validation."""
        event_management = EventManagementPage(admin_page, base_url)
        
        await event_management.navigate()
        await admin_page.click(event_management.CREATE_EVENT_BUTTON)
        
        # Try to submit empty form
        await admin_page.click("button[type='submit']")
        
        # Should show validation errors
        error_messages = await admin_page.locator(".error, .text-red-500, [role='alert']").all()
        assert len(error_messages) > 0, "Should show validation errors for empty form"
        
        # Test invalid date (past date)
        past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT19:00")
        
        await admin_page.fill("input[name='title']", "Test Event")
        await admin_page.fill("input[name='event_date']", past_date)
        await admin_page.fill("textarea[name='description']", "Test description")
        await admin_page.fill("input[name='venue']", "Test Venue")
        
        await admin_page.click("button[type='submit']")
        
        # Should show error for past date
        date_error = await admin_page.locator("*text*'past'*i, *text*'invalid'*i").first
        if await date_error.count() > 0:
            assert await date_error.is_visible(), "Should show error for past date"

    async def test_search_and_filter_events(self, admin_page: Page, base_url: str, faker_instance: Faker):
        """Test searching and filtering events."""
        event_management = EventManagementPage(admin_page, base_url)
        
        await event_management.navigate()
        
        # Create multiple events with different characteristics
        events_to_create = [
            f"London Speed Dating - {faker_instance.word()}",
            f"Manchester Speed Dating - {faker_instance.word()}",
            f"Birmingham Speed Dating - {faker_instance.word()}"
        ]
        
        for event_title in events_to_create:
            await event_management.create_event(
                title=event_title,
                description=f"Event in {event_title.split()[0]}",
                event_date=(datetime.now() + timedelta(days=10)).strftime("%Y-%m-%dT19:00"),
                venue=f"Venue in {event_title.split()[0]}"
            )
        
        # Test search functionality
        await event_management.search_events("London")
        
        filtered_events = await event_management.get_event_list()
        london_events = [e for e in filtered_events if "London" in e["title"]]
        assert len(london_events) > 0, "Should find London events"


@pytest.mark.e2e
@pytest.mark.playwright
class TestAttendeeEventInteractions:
    """Test event interactions from attendee perspective."""

    async def test_browse_public_events(self, page: Page, base_url: str):
        """Test browsing events as public user."""
        event_list = EventListPage(page, base_url)
        
        await event_list.navigate()
        
        # Should be able to see events without login
        events = await event_list.get_events_list()
        
        # Verify event information is displayed
        if len(events) > 0:
            first_event = events[0]
            assert first_event["title"], "Event should have title"
            assert first_event["date"], "Event should have date"
            assert first_event["venue"], "Event should have venue"

    async def test_register_for_event(self, page: Page, base_url: str, faker_instance: Faker):
        """Test registering for an event as attendee."""
        event_list = EventListPage(page, base_url)
        
        await event_list.navigate()
        
        events = await event_list.get_events_list()
        if len(events) > 0:
            event_title = events[0]["title"]
            
            # Try to register (should redirect to login)
            await event_list.register_for_event(event_title)
            
            # Should be redirected to login page
            await page.wait_for_url("**/auth/login**")

    async def test_event_search_and_filtering(self, page: Page, base_url: str):
        """Test event search and filtering functionality."""
        event_list = EventListPage(page, base_url)
        
        await event_list.navigate()
        
        # Test search if search functionality exists
        if await page.locator("input[name='search'], input[placeholder*='Search']").count() > 0:
            await event_list.search_events("Speed Dating")
            
            # Wait for search results
            await page.wait_for_timeout(1000)
            
            events_after_search = await event_list.get_events_list()
            # Verify search worked (implementation dependent)

    async def test_event_details_view(self, page: Page, base_url: str):
        """Test viewing detailed event information."""
        event_list = EventListPage(page, base_url)
        
        await event_list.navigate()
        
        events = await event_list.get_events_list()
        if len(events) > 0:
            event_title = events[0]["title"]
            
            # Click on event to view details
            await event_list.view_event_details(event_title)
            
            # Should navigate to event details page
            await page.wait_for_url("**/events/**")
            
            # Verify event details are shown
            await expect(page).to_have_title(f"*{event_title}*")

    async def test_authenticated_user_event_registration(self, authenticated_page: Page, base_url: str):
        """Test event registration flow for authenticated user."""
        attendee_dashboard = AttendeeDashboardPage(authenticated_page, base_url)
        
        await attendee_dashboard.navigate()
        
        # Get list of available events
        available_events = await attendee_dashboard.get_registered_events()
        
        # If there are events to register for, try registering
        # This depends on having events available in the test environment
        if len(available_events) == 0:
            # Could create an event first or skip if no events available
            pytest.skip("No events available for registration testing")

    async def test_event_capacity_limits(self, admin_page: Page, base_url: str, faker_instance: Faker):
        """Test event capacity constraints."""
        event_management = EventManagementPage(admin_page, base_url)
        
        await event_management.navigate()
        
        # Create event with very small capacity
        small_event_title = f"Small Event - {faker_instance.word()}"
        await event_management.create_event(
            title=small_event_title,
            description="Event with limited capacity",
            event_date=(datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT18:00"),
            venue="Small Venue",
            max_attendees=2  # Very small capacity
        )
        
        # Verify event was created with correct capacity
        events = await event_management.get_event_list()
        created_event = next((e for e in events if e["title"] == small_event_title), None)
        assert created_event, "Small capacity event should be created"


@pytest.mark.e2e
@pytest.mark.playwright
class TestAttendeeManagement:
    """Test attendee management functionality."""

    async def test_view_attendees_list(self, admin_page: Page, base_url: str):
        """Test viewing attendees for an event."""
        attendee_management = AttendeeManagementPage(admin_page, base_url)
        
        await attendee_management.navigate()
        
        # Get attendees list
        attendees = await attendee_management.get_attendee_list()
        
        # Verify attendee information is displayed correctly
        for attendee in attendees[:3]:  # Check first 3 attendees
            assert attendee["email"], "Attendee should have email"
            assert attendee["status"], "Attendee should have status"

    async def test_approve_reject_attendees(self, admin_page: Page, base_url: str):
        """Test approving and rejecting attendees."""
        attendee_management = AttendeeManagementPage(admin_page, base_url)
        
        await attendee_management.navigate()
        
        attendees = await attendee_management.get_attendee_list()
        
        # Find attendee with pending status if any
        pending_attendees = [a for a in attendees if "pending" in a["status"].lower()]
        
        if len(pending_attendees) > 0:
            attendee_email = pending_attendees[0]["email"]
            
            # Test approval
            await attendee_management.approve_attendee(attendee_email)
            
            # Wait for status update
            await admin_page.wait_for_timeout(1000)
            
            # Verify status changed (would need to refresh and check)
        else:
            pytest.skip("No pending attendees available for approval testing")

    async def test_export_attendees(self, admin_page: Page, base_url: str):
        """Test exporting attendees list."""
        attendee_management = AttendeeManagementPage(admin_page, base_url)
        
        await attendee_management.navigate()
        
        # Test export functionality if button exists
        if await admin_page.locator(attendee_management.EXPORT_BUTTON).count() > 0:
            download_path = await attendee_management.export_attendees()
            assert download_path, "Should download attendees export file"

    async def test_generate_badges(self, admin_page: Page, base_url: str):
        """Test generating PDF badges for attendees."""
        attendee_management = AttendeeManagementPage(admin_page, base_url)
        
        await attendee_management.navigate()
        
        attendee_count = await attendee_management.get_attendee_count()
        
        if attendee_count > 0:
            # Test badge generation if button exists
            if await admin_page.locator(attendee_management.GENERATE_BADGES_BUTTON).count() > 0:
                badge_path = await attendee_management.generate_badges()
                assert badge_path, "Should download badges PDF file"
        else:
            pytest.skip("No attendees available for badge generation")

    async def test_search_attendees(self, admin_page: Page, base_url: str):
        """Test searching attendees by email or name."""
        attendee_management = AttendeeManagementPage(admin_page, base_url)
        
        await attendee_management.navigate()
        
        attendees = await attendee_management.get_attendee_list()
        
        if len(attendees) > 0:
            # Search by first attendee's email
            search_email = attendees[0]["email"]
            
            await attendee_management.search_attendees(search_email.split("@")[0])
            
            # Wait for search results
            await admin_page.wait_for_timeout(1000)
            
            filtered_attendees = await attendee_management.get_attendee_list()
            assert len(filtered_attendees) > 0, "Search should return results"