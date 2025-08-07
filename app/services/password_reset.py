"""
Password Reset Service for local user password recovery.

Provides secure password reset functionality with token-based verification
for users who registered with email/password (not OAuth).
"""

import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.password_reset import PasswordResetToken
from app.models.user import User


class PasswordResetService:
    """Service for handling password reset operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def request_password_reset(
        self, 
        email: str, 
        base_url: str = "http://localhost:8000"
    ) -> bool:
        """
        Request a password reset for the given email address.
        
        Args:
            email: Email address of the user requesting reset
            base_url: Base URL for the reset link
            
        Returns:
            True if request was processed (always returns True for security)
            
        Raises:
            HTTPException: If there's a server error
        """
        try:
            # Find user by email (case-insensitive)
            from sqlalchemy import func, select
            
            user_query = select(User).where(func.lower(User.email) == email.lower())
            result = await self.session.execute(user_query)
            user = result.scalar_one_or_none()
            
            # Always return True for security (don't leak user existence)
            if not user:
                # Still log the attempt for security monitoring
                print(f"Password reset requested for non-existent email: {email}")
                return True
            
            # Check if user is OAuth only (no password set)
            if not user.hashed_password:
                print(f"Password reset requested for OAuth-only user: {email}")
                return True
            
            # Generate secure token
            token = self._generate_reset_token()
            
            # Clean up any existing tokens for this user
            await self._cleanup_user_tokens(user.id)
            
            # Create new reset token
            reset_token = PasswordResetToken.create_token(
                user_id=user.id,
                token=token,
                expires_in_minutes=60  # 1 hour expiration
            )
            
            self.session.add(reset_token)
            await self.session.commit()
            
            # Send reset email
            reset_url = f"{base_url}/auth/reset-password/{token}"
            await self._send_reset_email(user, reset_url)
            
            print(f"Password reset requested for user: {user.email}")
            return True
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            print(f"Database error in password reset request: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process password reset request"
            )
        except Exception as e:
            await self.session.rollback()
            print(f"Unexpected error in password reset request: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process password reset request"
            )
    
    async def validate_reset_token(self, token: str) -> Optional[PasswordResetToken]:
        """
        Validate a password reset token.
        
        Args:
            token: The reset token to validate
            
        Returns:
            PasswordResetToken if valid, None otherwise
        """
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload
            
            # Find token with user relationship
            query = select(PasswordResetToken).options(
                joinedload(PasswordResetToken.user)
            ).where(PasswordResetToken.token == token)
            
            result = await self.session.execute(query)
            reset_token = result.scalar_one_or_none()
            
            if not reset_token:
                return None
            
            if not reset_token.is_valid:
                return None
            
            return reset_token
            
        except SQLAlchemyError as e:
            print(f"Database error validating reset token: {str(e)}")
            return None
    
    async def reset_password(
        self, 
        token: str, 
        new_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Reset user password using a valid token.
        
        Args:
            token: The reset token
            new_password: New password to set
            ip_address: Client IP address for logging
            user_agent: Client user agent for logging
            
        Returns:
            True if password was reset successfully
            
        Raises:
            HTTPException: If token is invalid or operation fails
        """
        try:
            # Validate token
            reset_token = await self.validate_reset_token(token)
            if not reset_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired reset token"
                )
            
            # Get user
            user = reset_token.user
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User not found"
                )
            
            # Update user password using FastAPI-Users password hashing
            from fastapi_users.password import PasswordHelper
            
            password_helper = PasswordHelper()
            user.hashed_password = password_helper.hash(new_password)
            
            # Mark token as used
            reset_token.mark_used(ip_address=ip_address, user_agent=user_agent)
            
            # Clean up any other tokens for this user
            await self._cleanup_user_tokens(user.id, exclude_id=reset_token.id)
            
            await self.session.commit()
            
            print(f"Password reset completed for user: {user.email}")
            return True
            
        except HTTPException:
            await self.session.rollback()
            raise
        except SQLAlchemyError as e:
            await self.session.rollback()
            print(f"Database error resetting password: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password"
            )
        except Exception as e:
            await self.session.rollback()
            print(f"Unexpected error resetting password: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password"
            )
    
    def _generate_reset_token(self) -> str:
        """Generate a cryptographically secure reset token."""
        return secrets.token_urlsafe(32)
    
    async def _cleanup_user_tokens(
        self, 
        user_id: str, 
        exclude_id: Optional[str] = None
    ) -> None:
        """
        Clean up existing reset tokens for a user.
        
        Args:
            user_id: User ID to clean up tokens for
            exclude_id: Token ID to exclude from cleanup
        """
        try:
            from sqlalchemy import delete
            
            query = delete(PasswordResetToken).where(
                PasswordResetToken.user_id == user_id
            )
            
            if exclude_id:
                query = query.where(PasswordResetToken.id != exclude_id)
            
            await self.session.execute(query)
            
        except SQLAlchemyError as e:
            print(f"Error cleaning up user tokens: {str(e)}")
            # Don't raise - this is cleanup, not critical
    
    async def _send_reset_email(self, user: User, reset_url: str) -> None:
        """
        Send password reset email to user.
        
        Args:
            user: User to send email to
            reset_url: Complete reset URL with token
        """
        try:
            # For development/testing, just log the reset URL
            if not hasattr(settings, 'SMTP_HOST') or not settings.SMTP_HOST:
                print(f"\n{'='*60}")
                print(f"PASSWORD RESET REQUEST")
                print(f"{'='*60}")
                print(f"User: {user.email}")
                print(f"Name: {user.first_name} {user.last_name}")
                print(f"Reset URL: {reset_url}")
                print(f"{'='*60}\n")
                return
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = "Password Reset - Speed Dating"
            msg['From'] = getattr(settings, 'SMTP_FROM_EMAIL', 'noreply@speeddating.app')
            msg['To'] = user.email
            
            # Create email content
            text_content = f"""
Hi {user.first_name},

You requested a password reset for your Speed Dating account.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you didn't request this reset, please ignore this email.

Best regards,
Speed Dating Team
"""
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Password Reset</title>
</head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #0F172A; color: white; padding: 20px; text-align: center;">
        <h1 style="color: #DC2626; margin: 0;">Speed Dating</h1>
        <h2 style="margin: 10px 0 0 0;">Password Reset Request</h2>
    </div>
    
    <div style="padding: 20px; background-color: #f8f9fa;">
        <p>Hi {user.first_name},</p>
        
        <p>You requested a password reset for your Speed Dating account.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" 
               style="background-color: #DC2626; color: white; padding: 12px 24px; 
                      text-decoration: none; border-radius: 5px; display: inline-block;">
                Reset Your Password
            </a>
        </div>
        
        <p><strong>This link will expire in 1 hour.</strong></p>
        
        <p>If you didn't request this reset, please ignore this email.</p>
        
        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
        
        <p style="font-size: 12px; color: #666;">
            If the button doesn't work, copy and paste this URL into your browser:<br>
            <a href="{reset_url}" style="color: #DC2626;">{reset_url}</a>
        </p>
    </div>
</body>
</html>
"""
            
            # Attach content
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if getattr(settings, 'SMTP_TLS', False):
                    server.starttls()
                if getattr(settings, 'SMTP_USERNAME', None):
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            print(f"Password reset email sent to: {user.email}")
            
        except Exception as e:
            print(f"Failed to send password reset email to {user.email}: {str(e)}")
            # Don't raise - email failure shouldn't break the flow
            # The token is still valid, user can use the URL directly
    
    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired password reset tokens.
        
        Returns:
            Number of tokens cleaned up
        """
        try:
            from sqlalchemy import delete
            
            query = delete(PasswordResetToken).where(
                PasswordResetToken.expires_at < datetime.now(UTC)
            )
            
            result = await self.session.execute(query)
            await self.session.commit()
            
            count = result.rowcount
            if count > 0:
                print(f"Cleaned up {count} expired password reset tokens")
            
            return count
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            print(f"Error cleaning up expired tokens: {str(e)}")
            return 0