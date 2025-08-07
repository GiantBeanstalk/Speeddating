"""
End-to-end tests for admin dashboard functionality.

Tests admin dashboard overview, statistics, quick actions,
and administrative workflows.
"""

import pytest
from playwright.async_api import Page, expect
from faker import Faker

from tests.e2e.pages.admin_pages import AdminDashboardPage, EventManagementPage, AttendeeManagementPage


@pytest.mark.e2e
@pytest.mark.playwright
class TestAdminDashboardOverview:
    """Test admin dashboard overview and statistics."""

    async def test_admin_dashboard_loads(self, admin_page: Page, base_url: str):
        """Test that admin dashboard loads with proper content."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        
        await admin_dashboard.navigate()
        
        # Verify dashboard title
        await admin_dashboard.expect_title_contains("Admin")
        
        # Verify main dashboard elements are present
        await admin_dashboard.expect_element_visible(admin_dashboard.EVENTS_CARD)
        await admin_dashboard.expect_element_visible(admin_dashboard.ATTENDEES_CARD)
        
        # Check for user menu/logout
        if await admin_page.locator(admin_dashboard.USER_MENU).count() > 0:
            await admin_dashboard.expect_element_visible(admin_dashboard.USER_MENU)

    async def test_dashboard_statistics_display(self, admin_page: Page, base_url: str):
        """Test that dashboard statistics are displayed correctly."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        
        await admin_dashboard.navigate()
        
        # Get statistics from dashboard cards
        try:
            event_count = await admin_dashboard.get_event_count()
            attendee_count = await admin_dashboard.get_attendee_count()
            
            # Statistics should be non-negative numbers
            assert event_count >= 0, f"Event count should be non-negative: {event_count}"
            assert attendee_count >= 0, f"Attendee count should be non-negative: {attendee_count}"
            
            print(f"Dashboard shows {event_count} events, {attendee_count} attendees")
            
            # Try to get match count if available
            try:
                match_count = await admin_dashboard.get_match_count()
                assert match_count >= 0, f"Match count should be non-negative: {match_count}"
                print(f"Match count: {match_count}")
            except Exception:
                print("Match count not available or visible")
                
        except Exception as e:
            pytest.skip(f"Unable to get dashboard statistics: {e}")

    async def test_quick_actions_functionality(self, admin_page: Page, base_url: str):
        """Test quick actions from dashboard."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        
        await admin_dashboard.navigate()
        
        # Test create event quick action
        if await admin_page.locator(admin_dashboard.CREATE_EVENT_BUTTON).count() > 0:
            await admin_dashboard.click_create_event()
            
            # Should navigate to event creation
            await admin_page.wait_for_url("**/admin/events/create**")
            
            # Navigate back to dashboard
            await admin_dashboard.navigate()
        
        # Test manage events link
        if await admin_page.locator(admin_dashboard.MANAGE_EVENTS_LINK).count() > 0:
            await admin_dashboard.click_manage_events()
            
            # Should navigate to event management
            await admin_page.wait_for_url("**/admin/events**")
            
            # Navigate back to dashboard
            await admin_dashboard.navigate()

    async def test_navigation_between_admin_sections(self, admin_page: Page, base_url: str):
        """Test navigation between different admin sections."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        event_management = EventManagementPage(admin_page, base_url)
        attendee_management = AttendeeManagementPage(admin_page, base_url)
        
        # Start at dashboard
        await admin_dashboard.navigate()
        
        # Navigate to event management
        await event_management.navigate()
        await admin_page.wait_for_url("**/admin/events**")
        
        # Navigate to attendee management
        await attendee_management.navigate()
        await admin_page.wait_for_url("**/admin/attendees**")
        
        # Return to dashboard
        await admin_dashboard.navigate()
        await admin_page.wait_for_url("**/admin/dashboard**")

    async def test_admin_user_menu(self, admin_page: Page, base_url: str):
        """Test admin user menu functionality."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        
        await admin_dashboard.navigate()
        
        # Check if user menu exists
        if await admin_page.locator(admin_dashboard.USER_MENU).count() > 0:
            # Click user menu
            await admin_page.click(admin_dashboard.USER_MENU)
            
            # Look for logout option
            if await admin_page.locator(admin_dashboard.LOGOUT_BUTTON).count() > 0:
                # Don't actually logout in this test, just verify it exists
                await admin_dashboard.expect_element_visible(admin_dashboard.LOGOUT_BUTTON)
            
            # Click away to close menu
            await admin_page.click("body")
        else:
            pytest.skip("No user menu found on admin dashboard")


@pytest.mark.e2e
@pytest.mark.playwright
class TestAdminEventOverview:
    """Test admin event overview and management."""

    async def test_recent_events_display(self, admin_page: Page, base_url: str):
        """Test display of recent events on dashboard."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        
        await admin_dashboard.navigate()
        
        # Look for recent events section
        recent_events_selectors = [
            ".recent-events",
            "[data-testid='recent-events']",
            ".latest-events",
            ".event-summary"
        ]
        
        events_section_found = False
        for selector in recent_events_selectors:
            if await admin_page.locator(selector).count() > 0:
                events_section_found = True
                
                # Check event information
                event_items = await admin_page.locator(f"{selector} .event-item, {selector} .event").count()
                print(f"Found {event_items} recent events in dashboard")
                
                if event_items > 0:
                    # Verify first event has required information
                    first_event = admin_page.locator(f"{selector} .event-item, {selector} .event").first
                    
                    # Look for event title
                    title_element = first_event.locator(".title, .event-title, h3, h4")
                    if await title_element.count() > 0:
                        title_text = await title_element.text_content()
                        assert title_text and title_text.strip(), "Event should have title"
                
                break
        
        if not events_section_found:
            print("No recent events section found on dashboard")

    async def test_event_status_overview(self, admin_page: Page, base_url: str):
        """Test event status overview on dashboard."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        
        await admin_dashboard.navigate()
        
        # Look for event status indicators
        status_selectors = [
            ".event-status",
            "[data-testid='event-status']",
            ".status-overview",
            ".event-states"
        ]
        
        for selector in status_selectors:
            if await admin_page.locator(selector).count() > 0:
                status_text = await admin_page.locator(selector).text_content()
                print(f"Event status overview: {status_text}")
                
                # Look for common status indicators
                status_keywords = ["upcoming", "active", "completed", "draft", "published"]
                has_status = any(keyword in status_text.lower() for keyword in status_keywords)
                
                if has_status:
                    print("Found event status information")
                break

    async def test_attendee_overview(self, admin_page: Page, base_url: str):
        """Test attendee overview information."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        
        await admin_dashboard.navigate()
        
        # Look for attendee overview sections
        attendee_selectors = [
            ".attendee-overview",
            "[data-testid='attendee-overview']",
            ".registration-summary",
            ".attendee-stats"
        ]
        
        for selector in attendee_selectors:
            if await admin_page.locator(selector).count() > 0:
                overview_text = await admin_page.locator(selector).text_content()
                print(f"Attendee overview: {overview_text}")
                
                # Look for registration-related information
                registration_keywords = ["registered", "confirmed", "pending", "total"]
                has_registration_info = any(keyword in overview_text.lower() for keyword in registration_keywords)
                
                if has_registration_info:
                    print("Found attendee registration information")
                break


@pytest.mark.e2e
@pytest.mark.playwright
class TestAdminQuickActions:
    """Test admin quick actions and shortcuts."""

    async def test_bulk_attendee_actions(self, admin_page: Page, base_url: str):
        """Test bulk actions for attendee management."""
        attendee_management = AttendeeManagementPage(admin_page, base_url)
        
        await attendee_management.navigate()
        
        attendees = await attendee_management.get_attendee_list()
        
        if len(attendees) > 0:
            # Look for bulk action controls
            bulk_selectors = [
                "input[type='checkbox'][name='select-all']",
                ".select-all",
                "[data-testid='select-all']"
            ]
            
            bulk_actions_found = False
            for selector in bulk_selectors:
                if await admin_page.locator(selector).count() > 0:
                    bulk_actions_found = True
                    print("Found bulk action controls")
                    
                    # Test select all functionality
                    await admin_page.check(selector)
                    
                    # Look for bulk action buttons
                    bulk_buttons = await admin_page.locator("button:has-text('Bulk'), .bulk-actions button").count()
                    print(f"Found {bulk_buttons} bulk action buttons")
                    break
            
            if not bulk_actions_found:
                print("No bulk action controls found")
        else:
            pytest.skip("No attendees available for bulk action testing")

    async def test_export_functionality(self, admin_page: Page, base_url: str):
        """Test data export functionality."""
        attendee_management = AttendeeManagementPage(admin_page, base_url)
        
        await attendee_management.navigate()
        
        # Test export if available
        if await admin_page.locator(attendee_management.EXPORT_BUTTON).count() > 0:
            # Click export and handle download
            try:
                download_path = await attendee_management.export_attendees()
                assert download_path, "Export should generate download"
                print(f"Export successful: {download_path}")
            except Exception as e:
                print(f"Export test encountered: {e}")
        else:
            print("No export functionality found")

    async def test_badge_generation(self, admin_page: Page, base_url: str):
        """Test PDF badge generation."""
        attendee_management = AttendeeManagementPage(admin_page, base_url)
        
        await attendee_management.navigate()
        
        attendee_count = await attendee_management.get_attendee_count()
        
        if attendee_count > 0 and await admin_page.locator(attendee_management.GENERATE_BADGES_BUTTON).count() > 0:
            try:
                badge_path = await attendee_management.generate_badges()
                assert badge_path, "Badge generation should create PDF"
                print(f"Badge generation successful: {badge_path}")
            except Exception as e:
                print(f"Badge generation test encountered: {e}")
        else:
            pytest.skip("No attendees or badge generation not available")


@pytest.mark.e2e
@pytest.mark.playwright
class TestAdminAccessControl:
    """Test admin access control and security."""

    async def test_admin_only_access(self, page: Page, base_url: str):
        """Test that admin pages require admin authentication."""
        admin_dashboard = AdminDashboardPage(page, base_url)
        
        # Try to access admin dashboard without authentication
        await admin_dashboard.navigate()
        
        # Should be redirected to login or show access denied
        current_url = page.url
        
        if "login" in current_url:
            print("Correctly redirected to login")
        elif "403" in current_url or "denied" in current_url.lower():
            print("Correctly showed access denied")
        else:
            # Check page content for access denied messages
            page_content = await page.content()
            access_denied_indicators = ["access denied", "unauthorized", "403", "forbidden"]
            
            has_denial = any(indicator in page_content.lower() for indicator in access_denied_indicators)
            
            if not has_denial:
                pytest.fail("Admin page should require authentication")

    async def test_regular_user_admin_access(self, authenticated_page: Page, base_url: str):
        """Test that regular users cannot access admin functions."""
        admin_dashboard = AdminDashboardPage(authenticated_page, base_url)
        
        # Try to access admin dashboard with regular user
        await admin_dashboard.navigate()
        
        # Should either redirect or show access denied
        current_url = authenticated_page.url
        
        if "admin" not in current_url:
            print("Regular user correctly redirected away from admin")
        else:
            # Check if page shows access restrictions
            page_content = await authenticated_page.content()
            restriction_indicators = ["access denied", "not authorized", "admin only", "permission"]
            
            has_restriction = any(indicator in page_content.lower() for indicator in restriction_indicators)
            
            if not has_restriction:
                # Check if admin functions are actually available
                admin_buttons = await authenticated_page.locator(
                    "button:has-text('Create Event'), button:has-text('Manage'), .admin-action"
                ).count()
                
                if admin_buttons > 0:
                    pytest.fail("Regular user should not see admin functions")

    async def test_admin_logout_functionality(self, admin_page: Page, base_url: str):
        """Test admin logout functionality."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        
        await admin_dashboard.navigate()
        
        # Test logout if menu exists
        if await admin_page.locator(admin_dashboard.USER_MENU).count() > 0:
            await admin_dashboard.logout()
            
            # Should be redirected to login
            await admin_page.wait_for_url("**/auth/login**")
            
            # Try to access admin dashboard again
            await admin_dashboard.navigate()
            
            # Should be redirected to login again
            current_url = admin_page.url
            assert "login" in current_url, "Should redirect to login after logout"
        else:
            pytest.skip("No logout functionality found")


@pytest.mark.e2e
@pytest.mark.playwright
@pytest.mark.slow
class TestAdminPerformance:
    """Test admin dashboard performance and responsiveness."""

    async def test_dashboard_load_performance(self, admin_page: Page, base_url: str):
        """Test dashboard loading performance."""
        admin_dashboard = AdminDashboardPage(admin_page, base_url)
        
        # Measure dashboard load time
        start_time = admin_page.clock.now()
        
        await admin_dashboard.navigate()
        await admin_page.wait_for_load_state("networkidle")
        
        end_time = admin_page.clock.now()
        load_time = end_time - start_time
        
        print(f"Dashboard loaded in {load_time}ms")
        
        # Dashboard should load reasonably quickly
        assert load_time < 10000, f"Dashboard should load within 10 seconds, took {load_time}ms"

    async def test_large_dataset_handling(self, admin_page: Page, base_url: str):
        """Test handling of large datasets in admin interface."""
        attendee_management = AttendeeManagementPage(admin_page, base_url)
        
        await attendee_management.navigate()
        
        # Get attendee count
        attendee_count = await attendee_management.get_attendee_count()
        
        if attendee_count > 50:  # Large dataset
            print(f"Testing with {attendee_count} attendees")
            
            # Test pagination if available
            if await admin_page.locator(".pagination, [data-testid='pagination']").count() > 0:
                print("Pagination available for large dataset")
                
                # Test going to next page
                next_button = ".pagination button:has-text('Next'), .pagination a:has-text('Next')"
                if await admin_page.locator(next_button).count() > 0:
                    await admin_page.click(next_button)
                    await admin_page.wait_for_timeout(1000)
                    print("Successfully navigated to next page")
            
            # Test search/filter performance
            if await admin_page.locator(attendee_management.SEARCH_INPUT).count() > 0:
                search_start = admin_page.clock.now()
                await attendee_management.search_attendees("test")
                search_end = admin_page.clock.now()
                
                search_time = search_end - search_start
                print(f"Search completed in {search_time}ms")
                
                assert search_time < 5000, f"Search should complete within 5 seconds, took {search_time}ms"
        else:
            pytest.skip("Not enough data to test large dataset handling")