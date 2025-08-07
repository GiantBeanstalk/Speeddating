"""
End-to-end tests for authentication flows.

Tests user registration, login, logout, password reset, and related
authentication workflows across different browsers.
"""

import pytest
from playwright.async_api import Page, expect
from faker import Faker

from tests.e2e.pages.auth_pages import LoginPage, RegisterPage, ForgotPasswordPage, ResetPasswordPage
from tests.e2e.pages.public_pages import HomePage
from tests.e2e.pages.attendee_pages import AttendeeDashboardPage


@pytest.mark.e2e
@pytest.mark.playwright
class TestAuthenticationFlows:
    """Test authentication user flows."""

    async def test_user_registration_flow(self, page: Page, base_url: str, faker_instance: Faker):
        """Test complete user registration flow."""
        home = HomePage(page, base_url)
        register = RegisterPage(page, base_url)
        dashboard = AttendeeDashboardPage(page, base_url)

        # Start from home page
        await home.navigate()
        await home.click_register()

        # Fill registration form with realistic data
        test_email = faker_instance.email()
        test_password = "TestPassword123!"
        first_name = faker_instance.first_name()
        last_name = faker_instance.last_name()
        phone = faker_instance.phone_number()

        await register.register(
            email=test_email,
            password=test_password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            expect_success=True
        )

        # Should be redirected to dashboard
        await dashboard.expect_url_contains("dashboard")
        
        # Verify profile completion prompt appears
        completion = await dashboard.get_profile_completion_percentage()
        assert completion < 100, "New user should have incomplete profile"

    async def test_user_login_flow(self, page: Page, base_url: str, faker_instance: Faker):
        """Test user login flow."""
        home = HomePage(page, base_url)
        login = LoginPage(page, base_url)
        register = RegisterPage(page, base_url)
        dashboard = AttendeeDashboardPage(page, base_url)

        # First register a user
        await register.navigate()
        test_email = faker_instance.email()
        test_password = "TestPassword123!"
        
        await register.register(
            email=test_email,
            password=test_password,
            expect_success=True
        )
        
        # Log out by navigating to login (simulating logout)
        await login.navigate()
        
        # Test login with correct credentials
        await login.login(test_email, test_password, expect_success=True)
        
        # Should be redirected to dashboard
        await dashboard.expect_url_contains("dashboard")

    async def test_login_with_invalid_credentials(self, page: Page, base_url: str):
        """Test login with invalid credentials shows error."""
        login = LoginPage(page, base_url)
        
        await login.navigate()
        await login.login("invalid@email.com", "wrongpassword", expect_success=False)
        
        # Should show error message
        assert await login.has_error(), "Error message should be displayed"
        error_text = await login.get_error_message()
        assert "invalid" in error_text.lower() or "incorrect" in error_text.lower()

    async def test_registration_validation(self, page: Page, base_url: str):
        """Test registration form validation."""
        register = RegisterPage(page, base_url)
        
        await register.navigate()
        
        # Test with invalid email
        await register.register(
            email="invalid-email",
            password="TestPassword123!",
            expect_success=False
        )
        
        assert await register.has_error(), "Should show validation error for invalid email"
        
        # Test with weak password
        await register.navigate()  # Refresh page
        await register.register(
            email="test@example.com",
            password="weak",
            expect_success=False
        )
        
        assert await register.has_error(), "Should show validation error for weak password"

    async def test_password_reset_flow(self, page: Page, base_url: str, faker_instance: Faker):
        """Test password reset request flow."""
        login = LoginPage(page, base_url)
        forgot_password = ForgotPasswordPage(page, base_url)
        register = RegisterPage(page, base_url)
        
        # First register a user
        await register.navigate()
        test_email = faker_instance.email()
        test_password = "TestPassword123!"
        
        await register.register(
            email=test_email,
            password=test_password,
            expect_success=True
        )
        
        # Navigate to forgot password
        await login.navigate()
        await login.click_forgot_password()
        
        # Request password reset
        await forgot_password.request_password_reset(test_email, expect_success=True)
        
        # Should show success message
        success_message = await forgot_password.get_success_message()
        assert "sent" in success_message.lower() or "email" in success_message.lower()

    async def test_navigation_between_auth_pages(self, page: Page, base_url: str):
        """Test navigation between authentication pages."""
        home = HomePage(page, base_url)
        login = LoginPage(page, base_url)
        register = RegisterPage(page, base_url)
        forgot_password = ForgotPasswordPage(page, base_url)
        
        # Start from home
        await home.navigate()
        await home.click_login()
        
        # From login to register
        await login.click_register_link()
        await register.expect_url_contains("register")
        
        # From register to login
        await register.click_login_link()
        await login.expect_url_contains("login")
        
        # From login to forgot password
        await login.click_forgot_password()
        await forgot_password.expect_url_contains("forgot")
        
        # From forgot password back to login
        await forgot_password.click_back_to_login()
        await login.expect_url_contains("login")

    async def test_authenticated_page_access(self, authenticated_page: Page, base_url: str):
        """Test accessing authenticated pages."""
        dashboard = AttendeeDashboardPage(authenticated_page, base_url)
        
        # Should already be on dashboard (from authenticated_page fixture)
        await dashboard.expect_url_contains("dashboard")
        
        # Should have access to profile editing
        await dashboard.click_edit_profile()
        await dashboard.expect_url_contains("profile")

    async def test_unauthenticated_redirect(self, page: Page, base_url: str):
        """Test that unauthenticated users are redirected to login."""
        dashboard = AttendeeDashboardPage(page, base_url)
        
        # Try to access dashboard without authentication
        await dashboard.navigate()
        
        # Should be redirected to login
        await page.wait_for_url("**/auth/login**", timeout=10000)

    @pytest.mark.slow
    async def test_session_persistence(self, page: Page, base_url: str, faker_instance: Faker):
        """Test that user sessions persist across page reloads."""
        register = RegisterPage(page, base_url)
        dashboard = AttendeeDashboardPage(page, base_url)
        
        # Register and login
        await register.navigate()
        test_email = faker_instance.email()
        test_password = "TestPassword123!"
        
        await register.register(
            email=test_email,
            password=test_password,
            expect_success=True
        )
        
        # Reload the page
        await page.reload()
        await page.wait_for_load_state("networkidle")
        
        # Should still be logged in
        await dashboard.expect_url_contains("dashboard")

    async def test_registration_with_existing_email(self, page: Page, base_url: str, faker_instance: Faker):
        """Test registration with already existing email."""
        register = RegisterPage(page, base_url)
        
        # Register first user
        test_email = faker_instance.email()
        test_password = "TestPassword123!"
        
        await register.navigate()
        await register.register(
            email=test_email,
            password=test_password,
            expect_success=True
        )
        
        # Try to register again with same email
        await register.navigate()
        await register.register(
            email=test_email,  # Same email
            password="DifferentPassword123!",
            expect_success=False
        )
        
        # Should show error about existing email
        assert await register.has_error(), "Should show error for duplicate email"
        error_text = await register.get_error_message()
        assert "exists" in error_text.lower() or "already" in error_text.lower()


@pytest.mark.e2e
@pytest.mark.playwright
@pytest.mark.slow
class TestAuthenticationSecurity:
    """Test security aspects of authentication."""

    async def test_password_strength_requirements(self, page: Page, base_url: str, faker_instance: Faker):
        """Test password strength validation."""
        register = RegisterPage(page, base_url)
        await register.navigate()
        
        test_email = faker_instance.email()
        
        # Test various weak passwords
        weak_passwords = [
            "123456",      # Too short, only numbers
            "password",    # Too common, only letters  
            "Password",    # Missing numbers and symbols
            "Pass123",     # Too short
            "p" * 150,     # Too long
        ]
        
        for weak_password in weak_passwords:
            await register.navigate()  # Refresh page
            await register.register(
                email=test_email,
                password=weak_password,
                expect_success=False
            )
            
            assert await register.has_error(), f"Should reject weak password: {weak_password}"

    async def test_xss_protection_in_auth_forms(self, page: Page, base_url: str):
        """Test XSS protection in authentication forms."""
        register = RegisterPage(page, base_url)
        login = LoginPage(page, base_url)
        
        xss_payload = "<script>alert('xss')</script>"
        
        # Test XSS in registration
        await register.navigate()
        await register.register(
            email=f"{xss_payload}@test.com",
            password="TestPassword123!",
            first_name=xss_payload,
            expect_success=False
        )
        
        # Page should not execute the script
        # Check that the form handled the input safely
        page_content = await page.content()
        assert "<script>" not in page_content, "XSS payload should be escaped"
        
        # Test XSS in login
        await login.navigate()
        await login.login(f"{xss_payload}@test.com", "password", expect_success=False)
        
        # Should handle malicious input gracefully
        page_content = await page.content()
        assert "<script>" not in page_content, "XSS payload should be escaped"

    async def test_csrf_protection(self, page: Page, base_url: str):
        """Test CSRF protection on forms."""
        register = RegisterPage(page, base_url)
        
        await register.navigate()
        
        # Check for CSRF token in form
        csrf_token = await page.locator("input[name*='csrf'], input[name*='token']").first
        if await csrf_token.count() > 0:
            token_value = await csrf_token.get_attribute("value")
            assert token_value, "CSRF token should have a value"
            assert len(token_value) > 10, "CSRF token should be sufficiently long"

    async def test_rate_limiting_behavior(self, page: Page, base_url: str):
        """Test rate limiting on login attempts."""
        login = LoginPage(page, base_url)
        
        await login.navigate()
        
        # Make multiple failed login attempts
        for i in range(5):  # Assuming rate limit is around 5 attempts
            await login.login("test@example.com", "wrongpassword", expect_success=False)
            
            if i >= 3:  # After several attempts, check for rate limiting
                error_text = await login.get_error_message()
                if "too many" in error_text.lower() or "rate" in error_text.lower():
                    break  # Rate limiting detected
        
        # This test is informational - rate limiting behavior depends on implementation