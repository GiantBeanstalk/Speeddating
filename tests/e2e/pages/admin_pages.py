"""
Page objects for admin/organizer dashboard pages.
"""

from playwright.async_api import Page
from .base_page import BasePage
from typing import Optional, List, Dict


class AdminDashboardPage(BasePage):
    """Admin dashboard page interactions."""
    
    # Selectors
    EVENTS_CARD = ".dashboard-card:has-text('Events'), [data-testid='events-card']"
    ATTENDEES_CARD = ".dashboard-card:has-text('Attendees'), [data-testid='attendees-card']"
    MATCHES_CARD = ".dashboard-card:has-text('Matches'), [data-testid='matches-card']"
    CREATE_EVENT_BUTTON = "button:has-text('Create Event'), a:has-text('Create Event'), [data-testid='create-event']"
    MANAGE_EVENTS_LINK = "a:has-text('Manage Events'), [href*='events']"
    USER_MENU = ".user-menu, [data-testid='user-menu']"
    LOGOUT_BUTTON = "button:has-text('Logout'), a:has-text('Logout')"
    STATS_SECTION = ".stats, .statistics, [data-testid='stats']"
    
    async def navigate(self):
        """Navigate to admin dashboard."""
        await self.goto("/admin/dashboard")
    
    async def get_event_count(self) -> int:
        """Get total number of events from dashboard."""
        events_text = await self.get_text(f"{self.EVENTS_CARD} .count, {self.EVENTS_CARD} .number")
        return int(events_text.strip())
    
    async def get_attendee_count(self) -> int:
        """Get total number of attendees from dashboard."""
        attendees_text = await self.get_text(f"{self.ATTENDEES_CARD} .count, {self.ATTENDEES_CARD} .number")
        return int(attendees_text.strip())
    
    async def get_match_count(self) -> int:
        """Get total number of matches from dashboard."""
        matches_text = await self.get_text(f"{self.MATCHES_CARD} .count, {self.MATCHES_CARD} .number")
        return int(matches_text.strip())
    
    async def click_create_event(self):
        """Click create event button."""
        await self.click_and_wait(self.CREATE_EVENT_BUTTON, "**/admin/events/create**")
    
    async def click_manage_events(self):
        """Click manage events link."""
        await self.click_and_wait(self.MANAGE_EVENTS_LINK, "**/admin/events**")
    
    async def logout(self):
        """Logout from admin dashboard."""
        await self.page.click(self.USER_MENU)
        await self.click_and_wait(self.LOGOUT_BUTTON, "**/auth/login**")


class EventManagementPage(BasePage):
    """Event management page interactions."""
    
    # Selectors
    CREATE_EVENT_BUTTON = "button:has-text('Create Event'), [data-testid='create-event']"
    EVENT_TITLE_INPUT = "input[name='title'], #title"
    EVENT_DESCRIPTION_TEXTAREA = "textarea[name='description'], #description"
    EVENT_DATE_INPUT = "input[name='event_date'], input[type='datetime-local'], #event_date"
    VENUE_INPUT = "input[name='venue'], #venue"
    MAX_ATTENDEES_INPUT = "input[name='max_attendees'], #max_attendees"
    ROUND_DURATION_INPUT = "input[name='round_duration'], #round_duration"
    BREAK_DURATION_INPUT = "input[name='break_duration'], #break_duration"
    PRICE_INPUT = "input[name='price'], #price"
    SAVE_BUTTON = "button[type='submit']:has-text('Save'), button:has-text('Create Event')"
    CANCEL_BUTTON = "button:has-text('Cancel'), a:has-text('Cancel')"
    EVENT_LIST = ".event-list, [data-testid='event-list']"
    EVENT_ITEM = ".event-item, [data-testid='event-item']"
    EDIT_BUTTON = "button:has-text('Edit'), a:has-text('Edit')"
    DELETE_BUTTON = "button:has-text('Delete')"
    CONFIRM_DELETE = "button:has-text('Confirm'), button:has-text('Yes')"
    
    async def navigate(self):
        """Navigate to event management page."""
        await self.goto("/admin/events")
    
    async def create_event(
        self,
        title: str,
        description: str,
        event_date: str,
        venue: str,
        max_attendees: int = 50,
        round_duration: int = 5,
        break_duration: int = 2,
        price: float = 15.0
    ):
        """Create a new event with provided details."""
        await self.page.click(self.CREATE_EVENT_BUTTON)
        
        await self.fill_form_field(self.EVENT_TITLE_INPUT, title)
        await self.fill_form_field(self.EVENT_DESCRIPTION_TEXTAREA, description)
        await self.fill_form_field(self.EVENT_DATE_INPUT, event_date)
        await self.fill_form_field(self.VENUE_INPUT, venue)
        await self.fill_form_field(self.MAX_ATTENDEES_INPUT, str(max_attendees))
        await self.fill_form_field(self.ROUND_DURATION_INPUT, str(round_duration))
        await self.fill_form_field(self.BREAK_DURATION_INPUT, str(break_duration))
        await self.fill_form_field(self.PRICE_INPUT, str(price))
        
        await self.click_and_wait(self.SAVE_BUTTON, "**/admin/events**")
    
    async def get_event_list(self) -> List[Dict[str, str]]:
        """Get list of all events with their details."""
        events = []
        event_items = await self.page.locator(self.EVENT_ITEM).all()
        
        for item in event_items:
            title = await item.locator(".event-title, .title").text_content()
            date = await item.locator(".event-date, .date").text_content()
            venue = await item.locator(".event-venue, .venue").text_content()
            
            events.append({
                "title": title.strip() if title else "",
                "date": date.strip() if date else "",
                "venue": venue.strip() if venue else "",
            })
        
        return events
    
    async def edit_event(self, event_title: str):
        """Edit an event by title."""
        event_selector = f"{self.EVENT_ITEM}:has-text('{event_title}')"
        await self.page.locator(f"{event_selector} {self.EDIT_BUTTON}").click()
        await self.page.wait_for_url("**/admin/events/*/edit")
    
    async def delete_event(self, event_title: str):
        """Delete an event by title."""
        event_selector = f"{self.EVENT_ITEM}:has-text('{event_title}')"
        await self.page.locator(f"{event_selector} {self.DELETE_BUTTON}").click()
        await self.page.click(self.CONFIRM_DELETE)
        await self.wait_for_load()
    
    async def search_events(self, query: str):
        """Search events by query."""
        search_input = "input[placeholder*='Search'], input[name='search']"
        await self.fill_form_field(search_input, query)
        await self.press_key("Enter")
        await self.wait_for_load()


class AttendeeManagementPage(BasePage):
    """Attendee management page interactions."""
    
    # Selectors
    ATTENDEE_LIST = ".attendee-list, [data-testid='attendee-list']"
    ATTENDEE_ITEM = ".attendee-item, [data-testid='attendee-item']"
    SEARCH_INPUT = "input[placeholder*='Search'], input[name='search']"
    FILTER_SELECT = "select[name='filter'], #filter"
    EXPORT_BUTTON = "button:has-text('Export'), [data-testid='export-attendees']"
    GENERATE_BADGES_BUTTON = "button:has-text('Generate Badges'), [data-testid='generate-badges']"
    ATTENDEE_EMAIL = ".attendee-email, .email"
    ATTENDEE_NAME = ".attendee-name, .name"
    ATTENDEE_STATUS = ".attendee-status, .status"
    APPROVE_BUTTON = "button:has-text('Approve')"
    REJECT_BUTTON = "button:has-text('Reject')"
    
    async def navigate(self, event_id: Optional[str] = None):
        """Navigate to attendee management page."""
        url = "/admin/attendees"
        if event_id:
            url += f"?event_id={event_id}"
        await self.goto(url)
    
    async def get_attendee_list(self) -> List[Dict[str, str]]:
        """Get list of all attendees with their details."""
        attendees = []
        attendee_items = await self.page.locator(self.ATTENDEE_ITEM).all()
        
        for item in attendee_items:
            email = await item.locator(self.ATTENDEE_EMAIL).text_content()
            name = await item.locator(self.ATTENDEE_NAME).text_content()
            status = await item.locator(self.ATTENDEE_STATUS).text_content()
            
            attendees.append({
                "email": email.strip() if email else "",
                "name": name.strip() if name else "",
                "status": status.strip() if status else "",
            })
        
        return attendees
    
    async def search_attendees(self, query: str):
        """Search attendees by query."""
        await self.fill_form_field(self.SEARCH_INPUT, query)
        await self.press_key("Enter")
        await self.wait_for_load()
    
    async def filter_attendees(self, filter_option: str):
        """Filter attendees by status."""
        await self.select_dropdown(self.FILTER_SELECT, filter_option)
        await self.wait_for_load()
    
    async def approve_attendee(self, email: str):
        """Approve attendee by email."""
        attendee_selector = f"{self.ATTENDEE_ITEM}:has-text('{email}')"
        await self.page.locator(f"{attendee_selector} {self.APPROVE_BUTTON}").click()
        await self.wait_for_load()
    
    async def reject_attendee(self, email: str):
        """Reject attendee by email."""
        attendee_selector = f"{self.ATTENDEE_ITEM}:has-text('{email}')"
        await self.page.locator(f"{attendee_selector} {self.REJECT_BUTTON}").click()
        await self.wait_for_load()
    
    async def export_attendees(self):
        """Export attendees list."""
        async with self.page.expect_download() as download_info:
            await self.page.click(self.EXPORT_BUTTON)
        download = await download_info.value
        return await download.path()
    
    async def generate_badges(self):
        """Generate PDF badges for attendees."""
        async with self.page.expect_download() as download_info:
            await self.page.click(self.GENERATE_BADGES_BUTTON)
        download = await download_info.value
        return await download.path()
    
    async def get_attendee_count(self) -> int:
        """Get total number of attendees."""
        attendee_items = await self.page.locator(self.ATTENDEE_ITEM).count()
        return attendee_items