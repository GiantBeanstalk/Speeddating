"""
Page objects for attendee dashboard and matching pages.
"""

from playwright.async_api import Page
from .base_page import BasePage
from typing import Optional, List, Dict


class AttendeeDashboardPage(BasePage):
    """Attendee dashboard page interactions."""
    
    # Selectors
    PROFILE_CARD = ".profile-card, [data-testid='profile-card']"
    EVENTS_SECTION = ".events-section, [data-testid='events']"
    MATCHES_SECTION = ".matches-section, [data-testid='matches']"
    EDIT_PROFILE_BUTTON = "button:has-text('Edit Profile'), a:has-text('Edit Profile')"
    VIEW_MATCHES_BUTTON = "button:has-text('View Matches'), a:has-text('View Matches')"
    REGISTER_EVENT_BUTTON = "button:has-text('Register'), [data-testid='register-event']"
    QR_CODE = ".qr-code, [data-testid='qr-code']"
    PROFILE_COMPLETION = ".profile-completion, [data-testid='profile-completion']"
    
    async def navigate(self):
        """Navigate to attendee dashboard."""
        await self.goto("/dashboard")
    
    async def get_profile_completion_percentage(self) -> int:
        """Get profile completion percentage."""
        completion_text = await self.get_text(f"{self.PROFILE_COMPLETION} .percentage")
        return int(completion_text.replace("%", ""))
    
    async def click_edit_profile(self):
        """Click edit profile button."""
        await self.click_and_wait(self.EDIT_PROFILE_BUTTON, "**/profile/edit**")
    
    async def click_view_matches(self):
        """Click view matches button."""
        await self.click_and_wait(self.VIEW_MATCHES_BUTTON, "**/matches**")
    
    async def register_for_event(self, event_title: str):
        """Register for an event by title."""
        event_selector = f".event-card:has-text('{event_title}')"
        await self.page.locator(f"{event_selector} {self.REGISTER_EVENT_BUTTON}").click()
        await self.wait_for_load()
    
    async def has_qr_code(self) -> bool:
        """Check if QR code is displayed."""
        return await self.is_visible(self.QR_CODE)
    
    async def get_registered_events(self) -> List[str]:
        """Get list of registered events."""
        events = []
        event_cards = await self.page.locator(f"{self.EVENTS_SECTION} .event-card").all()
        
        for card in event_cards:
            title = await card.locator(".event-title").text_content()
            if title:
                events.append(title.strip())
        
        return events


class MatchingPage(BasePage):
    """Matching and preference selection page."""
    
    # Selectors
    ATTENDEE_CARD = ".attendee-card, [data-testid='attendee-card']"
    LIKE_BUTTON = "button:has-text('Like'), button.like, [data-testid='like']"
    PASS_BUTTON = "button:has-text('Pass'), button.pass, [data-testid='pass']"
    MAYBE_BUTTON = "button:has-text('Maybe'), button.maybe, [data-testid='maybe']"
    ROUND_TIMER = ".round-timer, [data-testid='timer']"
    ROUND_STATUS = ".round-status, [data-testid='round-status']"
    PREFERENCES_FORM = ".preferences-form, [data-testid='preferences']"
    SUBMIT_PREFERENCES = "button:has-text('Submit'), [data-testid='submit-preferences']"
    ATTENDEE_NAME = ".attendee-name, .name"
    ATTENDEE_BIO = ".attendee-bio, .bio"
    ATTENDEE_AGE = ".attendee-age, .age"
    MATCH_NOTIFICATION = ".match-notification, [data-testid='match-notification']"
    
    async def navigate(self, event_id: str):
        """Navigate to matching page for specific event."""
        await self.goto(f"/events/{event_id}/matching")
    
    async def get_current_attendee_info(self) -> Dict[str, str]:
        """Get current attendee information."""
        name = await self.get_text(f"{self.ATTENDEE_CARD} {self.ATTENDEE_NAME}")
        bio = await self.get_text(f"{self.ATTENDEE_CARD} {self.ATTENDEE_BIO}")
        age = await self.get_text(f"{self.ATTENDEE_CARD} {self.ATTENDEE_AGE}")
        
        return {
            "name": name.strip(),
            "bio": bio.strip(),
            "age": age.strip(),
        }
    
    async def like_attendee(self):
        """Click like button for current attendee."""
        await self.page.click(self.LIKE_BUTTON)
        await self.wait_for_load()
    
    async def pass_attendee(self):
        """Click pass button for current attendee."""
        await self.page.click(self.PASS_BUTTON)
        await self.wait_for_load()
    
    async def maybe_attendee(self):
        """Click maybe button for current attendee."""
        await self.page.click(self.MAYBE_BUTTON)
        await self.wait_for_load()
    
    async def get_round_timer(self) -> str:
        """Get current round timer value."""
        return await self.get_text(self.ROUND_TIMER)
    
    async def get_round_status(self) -> str:
        """Get current round status."""
        return await self.get_text(self.ROUND_STATUS)
    
    async def wait_for_match_notification(self, timeout: int = 10000):
        """Wait for match notification to appear."""
        await self.wait_for_element(self.MATCH_NOTIFICATION, timeout=timeout)
    
    async def has_match_notification(self) -> bool:
        """Check if match notification is displayed."""
        return await self.is_visible(self.MATCH_NOTIFICATION)
    
    async def submit_preferences(self):
        """Submit preference selections."""
        await self.page.click(self.SUBMIT_PREFERENCES)
        await self.wait_for_load()
    
    async def make_selections_for_round(self, selections: List[str]):
        """Make selections for all attendees in current round."""
        for selection in selections:
            attendee_info = await self.get_current_attendee_info()
            print(f"Making selection '{selection}' for {attendee_info['name']}")
            
            if selection.lower() == "like":
                await self.like_attendee()
            elif selection.lower() == "pass":
                await self.pass_attendee()
            elif selection.lower() == "maybe":
                await self.maybe_attendee()
            
            # Wait a moment before next selection
            await self.page.wait_for_timeout(500)


class ProfilePage(BasePage):
    """Profile editing and viewing page."""
    
    # Selectors
    BIO_TEXTAREA = "textarea[name='bio'], #bio"
    AGE_INPUT = "input[name='age'], #age"
    CATEGORY_SELECT = "select[name='category'], #category"
    INTERESTS_CHECKBOXES = "input[type='checkbox'][name*='interest']"
    PHONE_INPUT = "input[name='phone'], #phone"
    FETLIFE_INPUT = "input[name='fetlife_username'], #fetlife_username"
    PHOTO_UPLOAD = "input[type='file'][name='photo']"
    SAVE_BUTTON = "button:has-text('Save'), button[type='submit']"
    CANCEL_BUTTON = "button:has-text('Cancel'), a:has-text('Cancel')"
    SUCCESS_MESSAGE = ".success, .alert-success"
    ERROR_MESSAGE = ".error, .alert-danger"
    PROFILE_PHOTO = ".profile-photo, [data-testid='profile-photo']"
    
    async def navigate(self):
        """Navigate to profile edit page."""
        await self.goto("/profile/edit")
    
    async def update_profile(
        self,
        bio: Optional[str] = None,
        age: Optional[int] = None,
        category: Optional[str] = None,
        phone: Optional[str] = None,
        fetlife_username: Optional[str] = None,
        interests: Optional[List[str]] = None
    ):
        """Update profile with provided information."""
        if bio:
            await self.fill_form_field(self.BIO_TEXTAREA, bio)
        
        if age:
            await self.fill_form_field(self.AGE_INPUT, str(age))
        
        if category:
            await self.select_dropdown(self.CATEGORY_SELECT, category)
        
        if phone:
            await self.fill_form_field(self.PHONE_INPUT, phone)
        
        if fetlife_username:
            await self.fill_form_field(self.FETLIFE_INPUT, fetlife_username)
        
        if interests:
            # Uncheck all first
            checkboxes = await self.page.locator(self.INTERESTS_CHECKBOXES).all()
            for checkbox in checkboxes:
                await checkbox.uncheck()
            
            # Check selected interests
            for interest in interests:
                interest_checkbox = f"input[type='checkbox'][value='{interest}']"
                await self.page.check(interest_checkbox)
        
        await self.page.click(self.SAVE_BUTTON)
        await self.wait_for_element(self.SUCCESS_MESSAGE)
    
    async def upload_photo(self, photo_path: str):
        """Upload profile photo."""
        await self.upload_file(self.PHOTO_UPLOAD, photo_path)
    
    async def get_success_message(self) -> str:
        """Get success message text."""
        return await self.get_text(self.SUCCESS_MESSAGE)
    
    async def get_error_message(self) -> str:
        """Get error message text."""
        return await self.get_text(self.ERROR_MESSAGE)
    
    async def has_profile_photo(self) -> bool:
        """Check if profile photo is displayed."""
        return await self.is_visible(self.PROFILE_PHOTO)
    
    async def view_public_profile(self):
        """Navigate to public profile view."""
        await self.goto("/profile/public")
    
    async def get_profile_data(self) -> Dict[str, str]:
        """Get current profile data from form."""
        bio = await self.page.input_value(self.BIO_TEXTAREA)
        age = await self.page.input_value(self.AGE_INPUT)
        phone = await self.page.input_value(self.PHONE_INPUT)
        fetlife = await self.page.input_value(self.FETLIFE_INPUT)
        
        # Get selected category
        category = await self.page.locator(self.CATEGORY_SELECT).input_value()
        
        # Get selected interests
        selected_interests = []
        checkboxes = await self.page.locator(f"{self.INTERESTS_CHECKBOXES}:checked").all()
        for checkbox in checkboxes:
            value = await checkbox.get_attribute("value")
            if value:
                selected_interests.append(value)
        
        return {
            "bio": bio or "",
            "age": age or "",
            "category": category or "",
            "phone": phone or "",
            "fetlife_username": fetlife or "",
            "interests": selected_interests,
        }