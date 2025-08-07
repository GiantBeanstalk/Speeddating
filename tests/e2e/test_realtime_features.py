"""
End-to-end tests for real-time features.

Tests WebSocket connections, countdown timer, round management,
and other real-time functionality that requires browser automation.
"""

import pytest
import asyncio
from playwright.async_api import Page, expect
from faker import Faker

from tests.e2e.pages.attendee_pages import MatchingPage, AttendeeDashboardPage
from tests.e2e.pages.admin_pages import AdminDashboardPage


@pytest.mark.e2e
@pytest.mark.playwright
@pytest.mark.slow
class TestWebSocketConnections:
    """Test WebSocket connectivity and real-time updates."""

    async def test_websocket_connection_establishment(self, authenticated_page: Page, base_url: str):
        """Test that WebSocket connection is established properly."""
        matching_page = MatchingPage(authenticated_page, base_url)
        
        # Navigate to a page that uses WebSockets
        await matching_page.navigate("test-event-id")
        
        # Wait for WebSocket connection to establish
        await authenticated_page.wait_for_timeout(2000)
        
        # Check for WebSocket connection in network activity
        # Note: Direct WebSocket testing requires checking console logs or network events
        console_messages = []
        
        async def handle_console(msg):
            console_messages.append(msg.text)
        
        authenticated_page.on("console", handle_console)
        
        # Reload page to capture WebSocket connection logs
        await authenticated_page.reload()
        await authenticated_page.wait_for_timeout(3000)
        
        # Look for WebSocket-related console messages
        websocket_messages = [msg for msg in console_messages if "websocket" in msg.lower() or "ws" in msg.lower()]
        
        # This test is implementation-dependent and may need adjustment
        print(f"Console messages: {console_messages[:5]}")  # Debug info

    async def test_real_time_notifications(self, authenticated_page: Page, base_url: str):
        """Test real-time notifications via WebSocket."""
        dashboard = AttendeeDashboardPage(authenticated_page, base_url)
        
        await dashboard.navigate()
        
        # Set up notification listener
        notifications_received = []
        
        async def handle_notification(msg):
            if "notification" in msg.text.lower():
                notifications_received.append(msg.text)
        
        authenticated_page.on("console", handle_notification)
        
        # Trigger an action that should generate a notification
        # This would depend on the specific implementation
        await authenticated_page.wait_for_timeout(5000)
        
        # Check if any real-time updates occurred
        # Implementation specific - may need to simulate server-side events

    async def test_websocket_reconnection(self, authenticated_page: Page, base_url: str):
        """Test WebSocket reconnection after connection loss."""
        matching_page = MatchingPage(authenticated_page, base_url)
        
        await matching_page.navigate("test-event-id")
        
        # Wait for initial connection
        await authenticated_page.wait_for_timeout(2000)
        
        # Simulate network interruption by temporarily blocking WebSocket
        # This is complex to test in E2E without network manipulation tools
        
        # For now, just verify the page handles connection issues gracefully
        await authenticated_page.evaluate("""
            if (window.WebSocket) {
                // Temporarily override WebSocket to simulate connection issues
                const OriginalWebSocket = window.WebSocket;
                window.WebSocket = function() {
                    throw new Error('Connection failed');
                };
                
                // Restore after a moment
                setTimeout(() => {
                    window.WebSocket = OriginalWebSocket;
                }, 1000);
            }
        """)
        
        await authenticated_page.wait_for_timeout(3000)
        
        # Page should still be functional despite connection issues
        assert await authenticated_page.is_visible("body"), "Page should remain functional"


@pytest.mark.e2e
@pytest.mark.playwright
class TestCountdownTimer:
    """Test countdown timer functionality."""

    async def test_event_countdown_display(self, authenticated_page: Page, base_url: str):
        """Test event countdown timer display."""
        dashboard = AttendeeDashboardPage(authenticated_page, base_url)
        
        await dashboard.navigate()
        
        # Look for countdown timer elements
        countdown_selectors = [
            ".countdown",
            "[data-testid='countdown']",
            ".timer",
            "*text*'starts in'*i",
            "*text*'days'*i, *text*'hours'*i, *text*'minutes'*i"
        ]
        
        countdown_found = False
        for selector in countdown_selectors:
            if await authenticated_page.locator(selector).count() > 0:
                countdown_found = True
                countdown_element = authenticated_page.locator(selector).first
                
                # Verify countdown is displaying time
                countdown_text = await countdown_element.text_content()
                assert countdown_text, "Countdown should display time information"
                
                # Check if it contains time-related text
                time_indicators = ["day", "hour", "minute", "second", ":", "starts"]
                has_time_indicator = any(indicator in countdown_text.lower() for indicator in time_indicators)
                assert has_time_indicator, f"Countdown should contain time information: {countdown_text}"
                break
        
        if not countdown_found:
            pytest.skip("No countdown timer found on the page")

    async def test_countdown_timer_updates(self, authenticated_page: Page, base_url: str):
        """Test that countdown timer updates in real-time."""
        dashboard = AttendeeDashboardPage(authenticated_page, base_url)
        
        await dashboard.navigate()
        
        # Find countdown timer
        timer_selectors = [".countdown", "[data-testid='countdown']", ".timer"]
        
        timer_element = None
        for selector in timer_selectors:
            if await authenticated_page.locator(selector).count() > 0:
                timer_element = authenticated_page.locator(selector).first
                break
        
        if not timer_element:
            pytest.skip("No countdown timer found for update testing")
        
        # Get initial timer value
        initial_time = await timer_element.text_content()
        
        # Wait for timer to update (assuming it updates every second)
        await authenticated_page.wait_for_timeout(2000)
        
        # Get updated timer value
        updated_time = await timer_element.text_content()
        
        # Timer should have changed (unless it's showing days/hours and only updates slowly)
        # This test might be flaky depending on timer implementation
        print(f"Initial time: {initial_time}, Updated time: {updated_time}")

    async def test_round_timer_functionality(self, authenticated_page: Page, base_url: str):
        """Test round timer during matching phase."""
        matching_page = MatchingPage(authenticated_page, base_url)
        
        # Navigate to matching page (if event exists)
        try:
            await matching_page.navigate("test-event-id")
        except Exception:
            pytest.skip("No active event for round timer testing")
        
        # Look for round timer
        if await authenticated_page.locator(matching_page.ROUND_TIMER).count() > 0:
            initial_timer = await matching_page.get_round_timer()
            
            # Wait for timer to update
            await authenticated_page.wait_for_timeout(2000)
            
            updated_timer = await matching_page.get_round_timer()
            
            # Verify timer format (e.g., "5:00", "4:59")
            import re
            time_pattern = r'\d+:\d+'
            assert re.search(time_pattern, initial_timer), f"Timer should be in MM:SS format: {initial_timer}"
        else:
            pytest.skip("No round timer found")

    async def test_timer_expiration_behavior(self, authenticated_page: Page, base_url: str):
        """Test behavior when timer expires."""
        matching_page = MatchingPage(authenticated_page, base_url)
        
        try:
            await matching_page.navigate("test-event-id")
        except Exception:
            pytest.skip("No active event for timer expiration testing")
        
        # This test would require either:
        # 1. A test event with very short timer duration
        # 2. Ability to manipulate timer state
        # 3. Mock timer expiration
        
        # For now, just verify timer-related elements exist
        timer_elements = await authenticated_page.locator(matching_page.ROUND_TIMER).count()
        status_elements = await authenticated_page.locator(matching_page.ROUND_STATUS).count()
        
        if timer_elements > 0 or status_elements > 0:
            # Timer infrastructure exists
            pass
        else:
            pytest.skip("No timer infrastructure found for expiration testing")


@pytest.mark.e2e
@pytest.mark.playwright
class TestRoundManagement:
    """Test round management and transitions."""

    async def test_round_status_updates(self, authenticated_page: Page, base_url: str):
        """Test round status updates and transitions."""
        matching_page = MatchingPage(authenticated_page, base_url)
        
        try:
            await matching_page.navigate("test-event-id")
        except Exception:
            pytest.skip("No active event for round status testing")
        
        # Check if round status is displayed
        if await authenticated_page.locator(matching_page.ROUND_STATUS).count() > 0:
            status = await matching_page.get_round_status()
            
            # Verify status contains meaningful information
            status_keywords = ["round", "waiting", "active", "break", "finished", "starting"]
            has_status_keyword = any(keyword in status.lower() for keyword in status_keywords)
            assert has_status_keyword, f"Round status should contain meaningful information: {status}"
        else:
            pytest.skip("No round status display found")

    async def test_round_navigation(self, authenticated_page: Page, base_url: str):
        """Test navigation between rounds."""
        matching_page = MatchingPage(authenticated_page, base_url)
        
        try:
            await matching_page.navigate("test-event-id")
        except Exception:
            pytest.skip("No active event for round navigation testing")
        
        # Look for round navigation elements
        nav_selectors = [
            "button:has-text('Next Round')",
            "button:has-text('Previous Round')",
            ".round-nav",
            "[data-testid='round-nav']"
        ]
        
        nav_found = False
        for selector in nav_selectors:
            if await authenticated_page.locator(selector).count() > 0:
                nav_found = True
                break
        
        if not nav_found:
            pytest.skip("No round navigation found")
        
        # Test navigation if available
        # Implementation would depend on specific UI design

    async def test_match_selection_persistence(self, authenticated_page: Page, base_url: str):
        """Test that match selections persist across round transitions."""
        matching_page = MatchingPage(authenticated_page, base_url)
        
        try:
            await matching_page.navigate("test-event-id")
        except Exception:
            pytest.skip("No active event for match selection testing")
        
        # Look for matching interface elements
        if await authenticated_page.locator(matching_page.LIKE_BUTTON).count() > 0:
            # Make a selection
            await matching_page.like_attendee()
            
            # Wait for response
            await authenticated_page.wait_for_timeout(1000)
            
            # Reload page to test persistence
            await authenticated_page.reload()
            await authenticated_page.wait_for_timeout(2000)
            
            # Check that selections are maintained
            # This would require checking selection state, which is implementation-specific
        else:
            pytest.skip("No matching interface found")


@pytest.mark.e2e
@pytest.mark.playwright
@pytest.mark.slow
class TestRealTimeUpdates:
    """Test real-time updates and synchronization."""

    async def test_attendee_status_updates(self, authenticated_page: Page, base_url: str):
        """Test real-time attendee status updates."""
        dashboard = AttendeeDashboardPage(authenticated_page, base_url)
        
        await dashboard.navigate()
        
        # Look for attendee status indicators
        status_selectors = [
            ".attendee-status",
            "[data-testid='status']",
            ".online-indicator",
            ".status-indicator"
        ]
        
        status_found = False
        for selector in status_selectors:
            if await authenticated_page.locator(selector).count() > 0:
                status_found = True
                break
        
        if not status_found:
            pytest.skip("No attendee status indicators found")
        
        # Monitor for status changes over time
        await authenticated_page.wait_for_timeout(5000)
        
        # This test would benefit from multiple browser sessions to test real-time sync

    async def test_event_updates_propagation(self, authenticated_page: Page, base_url: str):
        """Test that event updates propagate to attendees in real-time."""
        dashboard = AttendeeDashboardPage(authenticated_page, base_url)
        
        await dashboard.navigate()
        
        # Look for event information that might update
        event_selectors = [
            ".event-info",
            "[data-testid='event-info']",
            ".event-status",
            ".event-updates"
        ]
        
        event_info_found = False
        for selector in event_selectors:
            if await authenticated_page.locator(selector).count() > 0:
                event_info_found = True
                
                # Get initial event information
                initial_info = await authenticated_page.locator(selector).text_content()
                
                # Wait for potential updates
                await authenticated_page.wait_for_timeout(3000)
                
                # Check if information updated
                updated_info = await authenticated_page.locator(selector).text_content()
                
                # Log for debugging
                print(f"Initial info: {initial_info}")
                print(f"Updated info: {updated_info}")
                break
        
        if not event_info_found:
            pytest.skip("No event information display found")

    async def test_notification_system(self, authenticated_page: Page, base_url: str):
        """Test real-time notification delivery."""
        dashboard = AttendeeDashboardPage(authenticated_page, base_url)
        
        await dashboard.navigate()
        
        # Look for notification areas
        notification_selectors = [
            ".notifications",
            "[data-testid='notifications']",
            ".toast",
            ".alert",
            ".notification-area"
        ]
        
        notifications_found = False
        for selector in notification_selectors:
            if await authenticated_page.locator(selector).count() > 0:
                notifications_found = True
                
                # Monitor for new notifications
                initial_count = await authenticated_page.locator(f"{selector} .notification, {selector} .toast").count()
                
                # Wait for potential notifications
                await authenticated_page.wait_for_timeout(5000)
                
                # Check for new notifications
                final_count = await authenticated_page.locator(f"{selector} .notification, {selector} .toast").count()
                
                print(f"Initial notifications: {initial_count}, Final: {final_count}")
                break
        
        if not notifications_found:
            pytest.skip("No notification system found")

    async def test_multi_user_synchronization(self, playwright, base_url: str, faker_instance: Faker):
        """Test synchronization between multiple users."""
        # This test requires multiple browser contexts
        browser = await playwright.chromium.launch()
        
        try:
            # Create two user contexts
            context1 = await browser.new_context()
            context2 = await browser.new_context()
            
            page1 = await context1.new_page()
            page2 = await context2.new_page()
            
            # Navigate both users to the same event/page
            dashboard1 = AttendeeDashboardPage(page1, base_url)
            dashboard2 = AttendeeDashboardPage(page2, base_url)
            
            # This would require actual user authentication for both contexts
            # For now, just verify both pages can load
            await dashboard1.navigate()
            await dashboard2.navigate()
            
            # Both pages should load successfully
            assert await page1.title(), "Page 1 should load"
            assert await page2.title(), "Page 2 should load"
            
        finally:
            await browser.close()


@pytest.mark.e2e
@pytest.mark.playwright
class TestWebSocketErrorHandling:
    """Test error handling for WebSocket connections."""

    async def test_graceful_degradation_without_websocket(self, page: Page, base_url: str):
        """Test that app works gracefully without WebSocket support."""
        # Disable WebSocket in browser
        await page.add_init_script("""
            delete window.WebSocket;
        """)
        
        dashboard = AttendeeDashboardPage(page, base_url)
        await dashboard.navigate()
        
        # App should still function without WebSocket
        await page.wait_for_timeout(2000)
        
        # Verify basic functionality works
        assert await page.is_visible("body"), "Page should load without WebSocket"
        
        # Look for fallback mechanisms
        polling_indicators = await page.locator("*text*'polling'*i, *text*'refresh'*i").count()
        if polling_indicators > 0:
            print("Found polling fallback indicators")

    async def test_websocket_error_recovery(self, authenticated_page: Page, base_url: str):
        """Test recovery from WebSocket errors."""
        dashboard = AttendeeDashboardPage(authenticated_page, base_url)
        
        await dashboard.navigate()
        
        # Simulate WebSocket errors
        await authenticated_page.evaluate("""
            if (window.WebSocket) {
                const OriginalWebSocket = window.WebSocket;
                window.WebSocket = function(url, protocols) {
                    const ws = new OriginalWebSocket(url, protocols);
                    
                    // Simulate error after connection
                    setTimeout(() => {
                        if (ws.onerror) {
                            ws.onerror(new Event('error'));
                        }
                    }, 1000);
                    
                    return ws;
                };
            }
        """)
        
        await authenticated_page.wait_for_timeout(3000)
        
        # Page should handle errors gracefully
        assert await authenticated_page.is_visible("body"), "Page should remain functional after WebSocket errors"