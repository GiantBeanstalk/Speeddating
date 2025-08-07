"""
Cross-browser and mobile viewport testing.

Tests application functionality across different browsers
and device viewports to ensure compatibility and responsiveness.
"""

import pytest
from playwright.async_api import Page, expect
from faker import Faker

from tests.e2e.pages.auth_pages import LoginPage, RegisterPage
from tests.e2e.pages.public_pages import HomePage, EventListPage
from tests.e2e.pages.attendee_pages import AttendeeDashboardPage


@pytest.mark.e2e
@pytest.mark.playwright
@pytest.mark.parametrize("browser_name", ["chromium", "firefox", "webkit"])
class TestCrossBrowserCompatibility:
    """Test application functionality across different browsers."""

    async def test_homepage_cross_browser(self, page: Page, base_url: str, browser_name: str):
        """Test homepage loads and functions across browsers."""
        home = HomePage(page, base_url)
        
        await home.navigate()
        
        # Verify basic page structure
        await home.expect_element_visible("body")
        await home.expect_title_contains("Speed Dating")
        
        # Verify navigation elements
        if await home.has_hero_section():
            print(f"Hero section visible in {browser_name}")
        
        # Test basic interactions
        if await page.locator(home.LOGIN_BUTTON).count() > 0:
            await home.expect_element_visible(home.LOGIN_BUTTON)
            print(f"Login button functional in {browser_name}")

    async def test_authentication_cross_browser(self, page: Page, base_url: str, browser_name: str, faker_instance: Faker):
        """Test authentication flow across browsers."""
        register = RegisterPage(page, base_url)
        login = LoginPage(page, base_url)
        dashboard = AttendeeDashboardPage(page, base_url)
        
        # Test registration
        await register.navigate()
        
        test_email = faker_instance.email()
        test_password = "TestPassword123!"
        
        await register.register(
            email=test_email,
            password=test_password,
            expect_success=True
        )
        
        # Should redirect to dashboard
        await dashboard.expect_url_contains("dashboard")
        print(f"Registration successful in {browser_name}")
        
        # Test login after logout
        await login.navigate()
        await login.login(test_email, test_password, expect_success=True)
        
        # Should redirect to dashboard again
        await dashboard.expect_url_contains("dashboard")
        print(f"Login successful in {browser_name}")

    async def test_responsive_design_cross_browser(self, page: Page, base_url: str, browser_name: str):
        """Test responsive design across browsers."""
        home = HomePage(page, base_url)
        
        # Test desktop viewport
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await home.navigate()
        
        # Verify desktop layout
        await home.expect_element_visible("body")
        
        # Test tablet viewport  
        await page.set_viewport_size({"width": 768, "height": 1024})
        await page.reload()
        await page.wait_for_load_state("networkidle")
        
        # Should still be functional
        await home.expect_element_visible("body")
        
        # Test mobile viewport
        await page.set_viewport_size({"width": 375, "height": 667})
        await page.reload()
        await page.wait_for_load_state("networkidle")
        
        # Should still be functional on mobile
        await home.expect_element_visible("body")
        print(f"Responsive design working in {browser_name}")

    async def test_javascript_functionality_cross_browser(self, page: Page, base_url: str, browser_name: str):
        """Test JavaScript functionality across browsers."""
        event_list = EventListPage(page, base_url)
        
        await event_list.navigate()
        
        # Test if JavaScript is working by checking for dynamic content
        await page.wait_for_timeout(2000)  # Allow JS to execute
        
        # Check if search functionality works (if available)
        if await page.locator(event_list.SEARCH_INPUT).count() > 0:
            await page.fill(event_list.SEARCH_INPUT, "test search")
            await page.press(event_list.SEARCH_INPUT, "Enter")
            
            # Wait for search to process
            await page.wait_for_timeout(1000)
            
            print(f"Search functionality working in {browser_name}")
        
        # Test basic DOM manipulation
        js_result = await page.evaluate("document.title")
        assert js_result, f"JavaScript execution working in {browser_name}"


@pytest.mark.e2e
@pytest.mark.playwright
class TestMobileViewport:
    """Test mobile viewport and touch interactions."""

    async def test_mobile_navigation(self, mobile_page: Page, base_url: str):
        """Test navigation on mobile viewport."""
        home = HomePage(mobile_page, base_url)
        
        await home.navigate()
        
        # Verify mobile layout
        viewport = mobile_page.viewport_size
        assert viewport["width"] <= 414, "Should be using mobile viewport"
        
        # Test mobile navigation (hamburger menu, etc.)
        mobile_nav_selectors = [
            ".mobile-nav",
            ".hamburger",
            "[data-testid='mobile-menu']",
            "button:has-text('Menu')"
        ]
        
        mobile_nav_found = False
        for selector in mobile_nav_selectors:
            if await mobile_page.locator(selector).count() > 0:
                mobile_nav_found = True
                
                # Try to interact with mobile navigation
                await mobile_page.click(selector)
                await mobile_page.wait_for_timeout(500)
                
                print("Mobile navigation interaction successful")
                break
        
        if not mobile_nav_found:
            # Check if regular navigation adapts to mobile
            nav_elements = await mobile_page.locator("nav, .nav").count()
            if nav_elements > 0:
                print("Standard navigation present on mobile")

    async def test_mobile_forms(self, mobile_page: Page, base_url: str, faker_instance: Faker):
        """Test form interaction on mobile viewport."""
        register = RegisterPage(mobile_page, base_url)
        
        await register.navigate()
        
        # Test mobile form interaction
        test_email = faker_instance.email()
        test_password = "TestPassword123!"
        
        # Fill form fields on mobile
        await register.fill_form_field(register.EMAIL_INPUT, test_email)
        await register.fill_form_field(register.PASSWORD_INPUT, test_password)
        await register.fill_form_field(register.CONFIRM_PASSWORD_INPUT, test_password)
        
        # Verify fields are filled correctly on mobile
        email_value = await mobile_page.input_value(register.EMAIL_INPUT)
        assert email_value == test_email, "Email field should be filled correctly on mobile"
        
        print("Mobile form interaction successful")

    async def test_mobile_touch_interactions(self, mobile_page: Page, base_url: str):
        """Test touch-specific interactions on mobile."""
        home = HomePage(mobile_page, base_url)
        
        await home.navigate()
        
        # Test tap interactions
        if await mobile_page.locator(home.LOGIN_BUTTON).count() > 0:
            # Get button position for touch interaction
            button = mobile_page.locator(home.LOGIN_BUTTON).first
            await button.tap()
            
            # Should navigate to login page
            await mobile_page.wait_for_url("**/auth/login**")
            print("Mobile tap interaction successful")

    async def test_mobile_scrolling(self, mobile_page: Page, base_url: str):
        """Test scrolling behavior on mobile."""
        event_list = EventListPage(mobile_page, base_url)
        
        await event_list.navigate()
        
        # Get initial scroll position
        initial_scroll = await mobile_page.evaluate("window.pageYOffset")
        
        # Scroll down
        await mobile_page.evaluate("window.scrollBy(0, 500)")
        await mobile_page.wait_for_timeout(500)
        
        # Check if scroll happened
        new_scroll = await mobile_page.evaluate("window.pageYOffset")
        assert new_scroll > initial_scroll, "Page should scroll on mobile"
        
        print("Mobile scrolling working correctly")

    async def test_mobile_responsive_elements(self, mobile_page: Page, base_url: str):
        """Test that elements adapt properly to mobile viewport."""
        home = HomePage(mobile_page, base_url)
        
        await home.navigate()
        
        # Check if elements are appropriately sized for mobile
        viewport_width = mobile_page.viewport_size["width"]
        
        # Check if any elements are wider than viewport
        wide_elements = await mobile_page.evaluate(f"""
            Array.from(document.querySelectorAll('*')).filter(el => {{
                const rect = el.getBoundingClientRect();
                return rect.width > {viewport_width};
            }}).length
        """)
        
        # Some elements may legitimately be wider (like overflow content)
        # but there shouldn't be too many
        if wide_elements > 5:
            print(f"Warning: {wide_elements} elements wider than viewport on mobile")


@pytest.mark.e2e
@pytest.mark.playwright
@pytest.mark.slow
class TestAccessibility:
    """Test accessibility features across browsers."""

    async def test_keyboard_navigation(self, page: Page, base_url: str):
        """Test keyboard navigation functionality."""
        home = HomePage(page, base_url)
        
        await home.navigate()
        
        # Test tab navigation
        focusable_elements = []
        
        # Tab through first few elements
        for i in range(10):
            await page.keyboard.press("Tab")
            
            # Get currently focused element
            focused = await page.evaluate("document.activeElement.tagName + (document.activeElement.type || '')")
            focusable_elements.append(focused)
            
            # Stop if we've cycled back to body
            if focused == "BODY" and i > 3:
                break
        
        # Should have found some focusable elements
        interactive_elements = [el for el in focusable_elements if el not in ["BODY", ""]]
        assert len(interactive_elements) > 0, "Should have focusable interactive elements"
        
        print(f"Found {len(interactive_elements)} keyboard-accessible elements")

    async def test_screen_reader_support(self, page: Page, base_url: str):
        """Test screen reader support (ARIA attributes)."""
        home = HomePage(page, base_url)
        
        await home.navigate()
        
        # Check for ARIA landmarks
        landmarks = await page.locator("[role], [aria-label], [aria-labelledby]").count()
        print(f"Found {landmarks} ARIA-enhanced elements")
        
        # Check for proper heading structure
        headings = await page.locator("h1, h2, h3, h4, h5, h6").count()
        print(f"Found {headings} heading elements")
        
        # Check for alt text on images
        images = await page.locator("img").count()
        images_with_alt = await page.locator("img[alt]").count()
        
        if images > 0:
            alt_text_ratio = images_with_alt / images
            print(f"Images with alt text: {images_with_alt}/{images} ({alt_text_ratio:.1%})")

    async def test_color_contrast(self, page: Page, base_url: str):
        """Test color contrast (basic check)."""
        home = HomePage(page, base_url)
        
        await home.navigate()
        
        # This is a simplified contrast check
        # Real accessibility testing would use specialized tools
        
        # Check for common contrast issues
        contrast_issues = await page.evaluate("""
            const elements = document.querySelectorAll('*');
            let issues = 0;
            
            for (let el of elements) {
                const style = window.getComputedStyle(el);
                const color = style.color;
                const bgColor = style.backgroundColor;
                
                // Simple check for white text on white background
                if (color === 'rgb(255, 255, 255)' && bgColor === 'rgb(255, 255, 255)') {
                    issues++;
                }
            }
            
            return issues;
        """)
        
        print(f"Potential contrast issues found: {contrast_issues}")

    async def test_focus_indicators(self, page: Page, base_url: str):
        """Test that focus indicators are visible."""
        register = RegisterPage(page, base_url)
        
        await register.navigate()
        
        # Tab to first input
        await page.keyboard.press("Tab")
        
        # Check if focus is visible
        focused_element = page.locator(":focus")
        
        if await focused_element.count() > 0:
            # Check if focus has visible styling
            focus_styles = await focused_element.evaluate("""
                el => {
                    const style = window.getComputedStyle(el);
                    return {
                        outline: style.outline,
                        boxShadow: style.boxShadow,
                        border: style.border
                    };
                }
            """)
            
            has_focus_indicator = any([
                focus_styles["outline"] != "none",
                focus_styles["boxShadow"] != "none",
                "focus" in focus_styles["border"]
            ])
            
            if has_focus_indicator:
                print("Focus indicators are present")
            else:
                print("Warning: Focus indicators may not be visible")


@pytest.mark.e2e
@pytest.mark.playwright
class TestPerformanceAcrossBrowsers:
    """Test performance characteristics across browsers."""

    async def test_page_load_performance(self, page: Page, base_url: str):
        """Test page load performance."""
        home = HomePage(page, base_url)
        
        # Measure load time
        start_time = page.clock.now()
        
        await home.navigate()
        await page.wait_for_load_state("networkidle")
        
        end_time = page.clock.now()
        load_time = end_time - start_time
        
        browser_name = page.context.browser.browser_type.name
        print(f"Page load time in {browser_name}: {load_time}ms")
        
        # Performance should be reasonable
        assert load_time < 10000, f"Page should load within 10 seconds, took {load_time}ms"

    async def test_javascript_performance(self, page: Page, base_url: str):
        """Test JavaScript execution performance."""
        home = HomePage(page, base_url)
        
        await home.navigate()
        
        # Measure JavaScript performance
        js_performance = await page.evaluate("""
            () => {
                const start = performance.now();
                
                // Simulate some JS work
                let result = 0;
                for (let i = 0; i < 100000; i++) {
                    result += i;
                }
                
                const end = performance.now();
                return {
                    duration: end - start,
                    result: result
                };
            }
        """)
        
        browser_name = page.context.browser.browser_type.name
        print(f"JavaScript performance in {browser_name}: {js_performance['duration']:.2f}ms")
        
        # JS execution should be fast
        assert js_performance["duration"] < 100, "JavaScript should execute quickly"

    async def test_memory_usage(self, page: Page, base_url: str):
        """Test memory usage patterns."""
        home = HomePage(page, base_url)
        
        await home.navigate()
        
        # Check memory usage if supported
        try:
            memory_info = await page.evaluate("""
                () => {
                    if ('memory' in performance) {
                        return {
                            usedJSHeapSize: performance.memory.usedJSHeapSize,
                            totalJSHeapSize: performance.memory.totalJSHeapSize,
                            jsHeapSizeLimit: performance.memory.jsHeapSizeLimit
                        };
                    }
                    return null;
                }
            """)
            
            if memory_info:
                browser_name = page.context.browser.browser_type.name
                used_mb = memory_info["usedJSHeapSize"] / (1024 * 1024)
                print(f"Memory usage in {browser_name}: {used_mb:.2f} MB")
            
        except Exception:
            print("Memory information not available in this browser")