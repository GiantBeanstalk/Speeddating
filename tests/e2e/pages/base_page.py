"""
Base page class with common functionality for all page objects.
"""

from playwright.async_api import Page, expect
from typing import Optional
import asyncio


class BasePage:
    """Base page object with common functionality."""
    
    def __init__(self, page: Page, base_url: str = "http://localhost:8000"):
        self.page = page
        self.base_url = base_url.rstrip('/')
    
    async def goto(self, path: str = ""):
        """Navigate to a specific path."""
        url = f"{self.base_url}{path}"
        await self.page.goto(url)
        await self.wait_for_load()
    
    async def wait_for_load(self, timeout: int = 30000):
        """Wait for page to load completely."""
        await self.page.wait_for_load_state("networkidle", timeout=timeout)
    
    async def wait_for_element(self, selector: str, timeout: int = 10000):
        """Wait for an element to be visible."""
        return await self.page.wait_for_selector(selector, timeout=timeout)
    
    async def click_and_wait(self, selector: str, wait_for_url: Optional[str] = None):
        """Click element and wait for navigation or specific URL."""
        if wait_for_url:
            async with self.page.expect_navigation():
                await self.page.click(selector)
            await self.page.wait_for_url(wait_for_url)
        else:
            await self.page.click(selector)
    
    async def fill_form_field(self, selector: str, value: str, clear_first: bool = True):
        """Fill a form field with proper error handling."""
        if clear_first:
            await self.page.fill(selector, "")
        await self.page.fill(selector, value)
        
        # Verify the value was set
        filled_value = await self.page.input_value(selector)
        if filled_value != value:
            raise AssertionError(f"Failed to fill field {selector}. Expected: {value}, Got: {filled_value}")
    
    async def select_dropdown(self, selector: str, value: str):
        """Select from dropdown."""
        await self.page.select_option(selector, value)
    
    async def upload_file(self, selector: str, file_path: str):
        """Upload file to input."""
        await self.page.set_input_files(selector, file_path)
    
    async def get_text(self, selector: str) -> str:
        """Get text content of element."""
        return await self.page.text_content(selector)
    
    async def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Get attribute value of element."""
        return await self.page.get_attribute(selector, attribute)
    
    async def is_visible(self, selector: str) -> bool:
        """Check if element is visible."""
        return await self.page.is_visible(selector)
    
    async def is_enabled(self, selector: str) -> bool:
        """Check if element is enabled."""
        return await self.page.is_enabled(selector)
    
    async def screenshot(self, path: Optional[str] = None, full_page: bool = True) -> bytes:
        """Take screenshot."""
        return await self.page.screenshot(path=path, full_page=full_page)
    
    async def wait_for_alert_and_accept(self, timeout: int = 5000):
        """Wait for alert dialog and accept it."""
        async def handle_dialog(dialog):
            await dialog.accept()
        
        self.page.on("dialog", handle_dialog)
        await asyncio.sleep(timeout / 1000)  # Wait for potential alert
    
    async def expect_url_contains(self, text: str):
        """Assert that current URL contains text."""
        await expect(self.page).to_have_url(f"**{text}**")
    
    async def expect_title_contains(self, text: str):
        """Assert that page title contains text."""
        await expect(self.page).to_have_title(f"*{text}*")
    
    async def expect_element_visible(self, selector: str):
        """Assert that element is visible."""
        await expect(self.page.locator(selector)).to_be_visible()
    
    async def expect_element_hidden(self, selector: str):
        """Assert that element is hidden."""
        await expect(self.page.locator(selector)).to_be_hidden()
    
    async def expect_text(self, selector: str, text: str):
        """Assert that element contains text."""
        await expect(self.page.locator(selector)).to_contain_text(text)
    
    async def expect_value(self, selector: str, value: str):
        """Assert that input has specific value."""
        await expect(self.page.locator(selector)).to_have_value(value)
    
    async def expect_count(self, selector: str, count: int):
        """Assert element count."""
        await expect(self.page.locator(selector)).to_have_count(count)
    
    async def scroll_to_bottom(self):
        """Scroll to bottom of page."""
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    
    async def scroll_to_element(self, selector: str):
        """Scroll element into view."""
        await self.page.locator(selector).scroll_into_view_if_needed()
    
    async def hover(self, selector: str):
        """Hover over element."""
        await self.page.hover(selector)
    
    async def double_click(self, selector: str):
        """Double click element."""
        await self.page.dblclick(selector)
    
    async def right_click(self, selector: str):
        """Right click element."""
        await self.page.click(selector, button="right")
    
    async def press_key(self, key: str):
        """Press keyboard key."""
        await self.page.keyboard.press(key)
    
    async def type_text(self, text: str, delay: int = 100):
        """Type text with delay between characters."""
        await self.page.keyboard.type(text, delay=delay)
    
    async def clear_input(self, selector: str):
        """Clear input field."""
        await self.page.fill(selector, "")
    
    async def get_current_url(self) -> str:
        """Get current page URL."""
        return self.page.url
    
    async def get_page_title(self) -> str:
        """Get page title."""
        return await self.page.title()
    
    async def reload_page(self):
        """Reload the current page."""
        await self.page.reload()
        await self.wait_for_load()
    
    async def go_back(self):
        """Navigate back in browser history."""
        await self.page.go_back()
        await self.wait_for_load()
    
    async def go_forward(self):
        """Navigate forward in browser history."""
        await self.page.go_forward()
        await self.wait_for_load()
    
    async def close_page(self):
        """Close the current page."""
        await self.page.close()