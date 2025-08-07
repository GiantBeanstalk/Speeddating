"""
Page objects for authentication-related pages.
"""

from playwright.async_api import Page
from .base_page import BasePage
from typing import Optional


class LoginPage(BasePage):
    """Login page interactions."""
    
    # Selectors
    EMAIL_INPUT = "input[name='email'], input[type='email'], #email"
    PASSWORD_INPUT = "input[name='password'], input[type='password'], #password"
    LOGIN_BUTTON = "button[type='submit'], input[type='submit'], button:has-text('Login')"
    FORGOT_PASSWORD_LINK = "a:has-text('Forgot Password'), a[href*='forgot']"
    REGISTER_LINK = "a:has-text('Register'), a:has-text('Sign Up'), a[href*='register']"
    ERROR_MESSAGE = ".error, .alert-danger, .text-red-500, [role='alert']"
    SUCCESS_MESSAGE = ".success, .alert-success, .text-green-500"
    
    async def navigate(self):
        """Navigate to login page."""
        await self.goto("/auth/login")
    
    async def login(self, email: str, password: str, expect_success: bool = True):
        """Perform login with credentials."""
        await self.fill_form_field(self.EMAIL_INPUT, email)
        await self.fill_form_field(self.PASSWORD_INPUT, password)
        
        if expect_success:
            await self.click_and_wait(self.LOGIN_BUTTON, "**/dashboard**")
        else:
            await self.page.click(self.LOGIN_BUTTON)
            await self.wait_for_element(self.ERROR_MESSAGE)
    
    async def click_forgot_password(self):
        """Click forgot password link."""
        await self.click_and_wait(self.FORGOT_PASSWORD_LINK, "**/forgot**")
    
    async def click_register_link(self):
        """Click register link."""
        await self.click_and_wait(self.REGISTER_LINK, "**/register**")
    
    async def get_error_message(self) -> str:
        """Get error message text."""
        await self.wait_for_element(self.ERROR_MESSAGE)
        return await self.get_text(self.ERROR_MESSAGE)
    
    async def has_error(self) -> bool:
        """Check if error message is displayed."""
        return await self.is_visible(self.ERROR_MESSAGE)


class RegisterPage(BasePage):
    """Registration page interactions."""
    
    # Selectors
    EMAIL_INPUT = "input[name='email'], input[type='email'], #email"
    PASSWORD_INPUT = "input[name='password'], input[type='password'], #password"
    CONFIRM_PASSWORD_INPUT = "input[name='password_confirm'], input[name='confirm_password'], #password_confirm"
    FIRST_NAME_INPUT = "input[name='first_name'], #first_name"
    LAST_NAME_INPUT = "input[name='last_name'], #last_name"
    PHONE_INPUT = "input[name='phone'], input[type='tel'], #phone"
    REGISTER_BUTTON = "button[type='submit'], input[type='submit'], button:has-text('Register')"
    LOGIN_LINK = "a:has-text('Login'), a:has-text('Sign In'), a[href*='login']"
    ERROR_MESSAGE = ".error, .alert-danger, .text-red-500, [role='alert']"
    SUCCESS_MESSAGE = ".success, .alert-success, .text-green-500"
    TERMS_CHECKBOX = "input[type='checkbox'][name*='terms'], #terms"
    
    async def navigate(self):
        """Navigate to register page."""
        await self.goto("/auth/register")
    
    async def register(
        self, 
        email: str, 
        password: str, 
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        accept_terms: bool = True,
        expect_success: bool = True
    ):
        """Perform registration with provided details."""
        await self.fill_form_field(self.EMAIL_INPUT, email)
        await self.fill_form_field(self.PASSWORD_INPUT, password)
        await self.fill_form_field(self.CONFIRM_PASSWORD_INPUT, password)
        
        if first_name and await self.is_visible(self.FIRST_NAME_INPUT):
            await self.fill_form_field(self.FIRST_NAME_INPUT, first_name)
        
        if last_name and await self.is_visible(self.LAST_NAME_INPUT):
            await self.fill_form_field(self.LAST_NAME_INPUT, last_name)
        
        if phone and await self.is_visible(self.PHONE_INPUT):
            await self.fill_form_field(self.PHONE_INPUT, phone)
        
        if accept_terms and await self.is_visible(self.TERMS_CHECKBOX):
            await self.page.check(self.TERMS_CHECKBOX)
        
        if expect_success:
            await self.click_and_wait(self.REGISTER_BUTTON, "**/dashboard**")
        else:
            await self.page.click(self.REGISTER_BUTTON)
            await self.wait_for_element(self.ERROR_MESSAGE, timeout=5000)
    
    async def click_login_link(self):
        """Click login link."""
        await self.click_and_wait(self.LOGIN_LINK, "**/login**")
    
    async def get_error_message(self) -> str:
        """Get error message text."""
        await self.wait_for_element(self.ERROR_MESSAGE)
        return await self.get_text(self.ERROR_MESSAGE)
    
    async def has_error(self) -> bool:
        """Check if error message is displayed."""
        return await self.is_visible(self.ERROR_MESSAGE)


class ForgotPasswordPage(BasePage):
    """Forgot password page interactions."""
    
    # Selectors
    EMAIL_INPUT = "input[name='email'], input[type='email'], #email"
    SUBMIT_BUTTON = "button[type='submit'], input[type='submit'], button:has-text('Send Reset')"
    BACK_TO_LOGIN_LINK = "a:has-text('Back to Login'), a[href*='login']"
    ERROR_MESSAGE = ".error, .alert-danger, .text-red-500, [role='alert']"
    SUCCESS_MESSAGE = ".success, .alert-success, .text-green-500"
    
    async def navigate(self):
        """Navigate to forgot password page."""
        await self.goto("/auth/forgot-password")
    
    async def request_password_reset(self, email: str, expect_success: bool = True):
        """Request password reset for email."""
        await self.fill_form_field(self.EMAIL_INPUT, email)
        await self.page.click(self.SUBMIT_BUTTON)
        
        if expect_success:
            await self.wait_for_element(self.SUCCESS_MESSAGE)
        else:
            await self.wait_for_element(self.ERROR_MESSAGE)
    
    async def click_back_to_login(self):
        """Click back to login link."""
        await self.click_and_wait(self.BACK_TO_LOGIN_LINK, "**/login**")
    
    async def get_success_message(self) -> str:
        """Get success message text."""
        await self.wait_for_element(self.SUCCESS_MESSAGE)
        return await self.get_text(self.SUCCESS_MESSAGE)
    
    async def get_error_message(self) -> str:
        """Get error message text."""
        await self.wait_for_element(self.ERROR_MESSAGE)
        return await self.get_text(self.ERROR_MESSAGE)


class ResetPasswordPage(BasePage):
    """Reset password page interactions."""
    
    # Selectors
    PASSWORD_INPUT = "input[name='password'], input[type='password'], #password"
    CONFIRM_PASSWORD_INPUT = "input[name='password_confirm'], input[name='confirm_password'], #password_confirm"
    RESET_BUTTON = "button[type='submit'], input[type='submit'], button:has-text('Reset Password')"
    ERROR_MESSAGE = ".error, .alert-danger, .text-red-500, [role='alert']"
    SUCCESS_MESSAGE = ".success, .alert-success, .text-green-500"
    
    async def navigate(self, token: str):
        """Navigate to reset password page with token."""
        await self.goto(f"/auth/reset-password?token={token}")
    
    async def reset_password(self, new_password: str, expect_success: bool = True):
        """Reset password with new password."""
        await self.fill_form_field(self.PASSWORD_INPUT, new_password)
        await self.fill_form_field(self.CONFIRM_PASSWORD_INPUT, new_password)
        
        if expect_success:
            await self.click_and_wait(self.RESET_BUTTON, "**/login**")
        else:
            await self.page.click(self.RESET_BUTTON)
            await self.wait_for_element(self.ERROR_MESSAGE)
    
    async def get_success_message(self) -> str:
        """Get success message text."""
        await self.wait_for_element(self.SUCCESS_MESSAGE)
        return await self.get_text(self.SUCCESS_MESSAGE)
    
    async def get_error_message(self) -> str:
        """Get error message text."""
        await self.wait_for_element(self.ERROR_MESSAGE)
        return await self.get_text(self.ERROR_MESSAGE)
    
    async def has_expired_token_error(self) -> bool:
        """Check if token has expired."""
        error_text = await self.get_error_message()
        return "expired" in error_text.lower() or "invalid" in error_text.lower()