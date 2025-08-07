"""
Page objects for public-facing pages.
"""

from playwright.async_api import Page
from .base_page import BasePage
from typing import Optional, List, Dict


class HomePage(BasePage):
    """Home page interactions."""
    
    # Selectors
    HERO_SECTION = ".hero, [data-testid='hero']"
    CTA_BUTTON = "button:has-text('Get Started'), a:has-text('Get Started'), .cta-button"
    LOGIN_BUTTON = "button:has-text('Login'), a:has-text('Login')"
    REGISTER_BUTTON = "button:has-text('Register'), a:has-text('Sign Up')"
    UPCOMING_EVENTS = ".upcoming-events, [data-testid='upcoming-events']"
    EVENT_CARD = ".event-card, [data-testid='event-card']"
    NAVIGATION_MENU = ".nav-menu, nav"
    
    async def navigate(self):
        """Navigate to home page."""
        await self.goto("/")
    
    async def click_login(self):
        """Click login button."""
        await self.click_and_wait(self.LOGIN_BUTTON, "**/auth/login**")
    
    async def click_register(self):
        """Click register button."""
        await self.click_and_wait(self.REGISTER_BUTTON, "**/auth/register**")
    
    async def click_get_started(self):
        """Click main CTA button."""
        await self.click_and_wait(self.CTA_BUTTON, "**/auth/register**")
    
    async def get_upcoming_events(self) -> List[Dict[str, str]]:
        """Get upcoming events displayed on home page."""
        events = []
        event_cards = await self.page.locator(f"{self.UPCOMING_EVENTS} {self.EVENT_CARD}").all()
        
        for card in event_cards:
            title = await card.locator(".event-title, .title").text_content()
            date = await card.locator(".event-date, .date").text_content()
            venue = await card.locator(".event-venue, .venue").text_content()
            
            events.append({
                "title": title.strip() if title else "",
                "date": date.strip() if date else "",
                "venue": venue.strip() if venue else "",
            })
        
        return events
    
    async def navigate_to_event(self, event_title: str):
        """Navigate to specific event page."""
        event_selector = f"{self.EVENT_CARD}:has-text('{event_title}')"
        await self.page.locator(event_selector).click()
        await self.page.wait_for_url("**/events/**")
    
    async def has_hero_section(self) -> bool:
        """Check if hero section is displayed."""
        return await self.is_visible(self.HERO_SECTION)


class EventListPage(BasePage):
    """Event listing page interactions."""
    
    # Selectors
    EVENT_LIST = ".event-list, [data-testid='event-list']"
    EVENT_ITEM = ".event-item, [data-testid='event-item']"
    SEARCH_INPUT = "input[placeholder*='Search'], input[name='search']"
    FILTER_SELECT = "select[name='filter'], #filter"
    SORT_SELECT = "select[name='sort'], #sort"
    REGISTER_BUTTON = "button:has-text('Register'), [data-testid='register']"
    EVENT_TITLE = ".event-title, .title"
    EVENT_DATE = ".event-date, .date"
    EVENT_VENUE = ".event-venue, .venue"
    EVENT_PRICE = ".event-price, .price"
    EVENT_SPOTS = ".event-spots, .available-spots"
    PAGINATION = ".pagination, [data-testid='pagination']"
    
    async def navigate(self):
        """Navigate to events list page."""
        await self.goto("/events")
    
    async def get_events_list(self) -> List[Dict[str, str]]:
        """Get list of all events with their details."""
        events = []
        event_items = await self.page.locator(self.EVENT_ITEM).all()
        
        for item in event_items:
            title = await item.locator(self.EVENT_TITLE).text_content()
            date = await item.locator(self.EVENT_DATE).text_content()
            venue = await item.locator(self.EVENT_VENUE).text_content()
            price = await item.locator(self.EVENT_PRICE).text_content()
            spots = await item.locator(self.EVENT_SPOTS).text_content()
            
            events.append({
                "title": title.strip() if title else "",
                "date": date.strip() if date else "",
                "venue": venue.strip() if venue else "",
                "price": price.strip() if price else "",
                "available_spots": spots.strip() if spots else "",
            })
        
        return events
    
    async def search_events(self, query: str):
        """Search events by query."""
        await self.fill_form_field(self.SEARCH_INPUT, query)
        await self.press_key("Enter")
        await self.wait_for_load()
    
    async def filter_events(self, filter_option: str):
        """Filter events by criteria."""
        await self.select_dropdown(self.FILTER_SELECT, filter_option)
        await self.wait_for_load()
    
    async def sort_events(self, sort_option: str):
        """Sort events by criteria."""
        await self.select_dropdown(self.SORT_SELECT, sort_option)
        await self.wait_for_load()
    
    async def register_for_event(self, event_title: str):
        """Register for an event by title."""
        event_selector = f"{self.EVENT_ITEM}:has-text('{event_title}')"
        register_button = f"{event_selector} {self.REGISTER_BUTTON}"
        await self.click_and_wait(register_button, "**/auth/login**")
    
    async def view_event_details(self, event_title: str):
        """View event details page."""
        event_selector = f"{self.EVENT_ITEM}:has-text('{event_title}') {self.EVENT_TITLE}"
        await self.page.locator(event_selector).click()
        await self.page.wait_for_url("**/events/**")
    
    async def go_to_next_page(self):
        """Go to next page of events."""
        next_button = f"{self.PAGINATION} button:has-text('Next'), {self.PAGINATION} a:has-text('Next')"
        await self.page.click(next_button)
        await self.wait_for_load()
    
    async def go_to_previous_page(self):
        """Go to previous page of events."""
        prev_button = f"{self.PAGINATION} button:has-text('Previous'), {self.PAGINATION} a:has-text('Previous')"
        await self.page.click(prev_button)
        await self.wait_for_load()
    
    async def get_current_page(self) -> int:
        """Get current page number."""
        active_page = f"{self.PAGINATION} .active, {self.PAGINATION} .current-page"
        page_text = await self.get_text(active_page)
        return int(page_text.strip())


class PublicProfilePage(BasePage):
    """Public profile viewing page."""
    
    # Selectors
    PROFILE_PHOTO = ".profile-photo, [data-testid='profile-photo']"
    PROFILE_NAME = ".profile-name, .name"
    PROFILE_AGE = ".profile-age, .age"
    PROFILE_BIO = ".profile-bio, .bio"
    PROFILE_INTERESTS = ".profile-interests, .interests"
    INTEREST_TAG = ".interest-tag, .tag"
    QR_CODE = ".qr-code, [data-testid='qr-code']"
    CONTACT_BUTTON = "button:has-text('Contact'), [data-testid='contact']"
    BACK_BUTTON = "button:has-text('Back'), a:has-text('Back')"
    
    async def navigate(self, user_id: str):
        """Navigate to public profile page."""
        await self.goto(f"/profile/{user_id}")
    
    async def navigate_by_qr(self, qr_token: str):
        """Navigate to profile via QR code token."""
        await self.goto(f"/qr/{qr_token}")
    
    async def get_profile_info(self) -> Dict[str, str]:
        """Get profile information."""
        name = await self.get_text(self.PROFILE_NAME)
        age = await self.get_text(self.PROFILE_AGE)
        bio = await self.get_text(self.PROFILE_BIO)
        
        # Get interests
        interests = []
        interest_tags = await self.page.locator(f"{self.PROFILE_INTERESTS} {self.INTEREST_TAG}").all()
        for tag in interest_tags:
            interest = await tag.text_content()
            if interest:
                interests.append(interest.strip())
        
        return {
            "name": name.strip(),
            "age": age.strip(),
            "bio": bio.strip(),
            "interests": interests,
        }
    
    async def has_profile_photo(self) -> bool:
        """Check if profile photo is displayed."""
        return await self.is_visible(self.PROFILE_PHOTO)
    
    async def has_qr_code(self) -> bool:
        """Check if QR code is displayed."""
        return await self.is_visible(self.QR_CODE)
    
    async def click_contact(self):
        """Click contact button."""
        await self.page.click(self.CONTACT_BUTTON)
    
    async def go_back(self):
        """Click back button."""
        await self.page.click(self.BACK_BUTTON)
        await self.wait_for_load()
    
    async def get_page_title(self) -> str:
        """Get page title."""
        return await self.page.title()
    
    async def is_profile_complete(self) -> bool:
        """Check if profile appears complete."""
        has_name = await self.is_visible(self.PROFILE_NAME)
        has_bio = await self.is_visible(self.PROFILE_BIO)
        has_age = await self.is_visible(self.PROFILE_AGE)
        
        return has_name and has_bio and has_age
    
    async def get_interests_count(self) -> int:
        """Get number of interests displayed."""
        return await self.page.locator(f"{self.PROFILE_INTERESTS} {self.INTEREST_TAG}").count()