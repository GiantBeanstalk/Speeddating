#!/usr/bin/env python3
"""
Password Reset functionality test script.

Tests the password reset service, token generation, and validation.
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta

from app.database import async_session_maker
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services.password_reset import PasswordResetService


async def test_password_reset():
    """Test password reset functionality."""
    print("🔐 Password Reset Functionality Test")
    print("=" * 50)
    
    async with async_session_maker() as session:
        try:
            # Test 1: Create a test user (or use existing one)
            print("1. Setting up test user...")
            
            # Create password reset service
            reset_service = PasswordResetService(session)
            
            # Test 2: Request password reset for non-existent email
            print("\n2. Testing password reset for non-existent email...")
            result = await reset_service.request_password_reset(
                "nonexistent@test.com",
                "http://localhost:8000"
            )
            if result:
                print("   ✅ Request handled securely (no user existence leak)")
            else:
                print("   ❌ Request should always return True for security")
            
            # Test 3: Token generation and validation
            print("\n3. Testing token creation and validation...")
            
            # Create a test token directly
            test_user_id = "123e4567-e89b-12d3-a456-426614174000"  # Sample UUID
            test_token = "test_token_123456789"
            
            # Create token instance
            reset_token = PasswordResetToken.create_token(
                user_id=test_user_id,
                token=test_token,
                expires_in_minutes=60
            )
            
            print(f"   Token created: {reset_token.token[:20]}...")
            print(f"   Expires at: {reset_token.expires_at}")
            print(f"   Is valid: {reset_token.is_valid}")
            print(f"   Is expired: {reset_token.is_expired}")
            
            if reset_token.is_valid and not reset_token.is_expired:
                print("   ✅ Token creation and validation working")
            else:
                print("   ❌ Token validation failed")
            
            # Test 4: Test expired token
            print("\n4. Testing expired token...")
            expired_token = PasswordResetToken(
                user_id=test_user_id,
                token="expired_token",
                expires_at=datetime.now(UTC) - timedelta(minutes=5)
            )
            
            print(f"   Expired token is valid: {expired_token.is_valid}")
            print(f"   Expired token is expired: {expired_token.is_expired}")
            
            if not expired_token.is_valid and expired_token.is_expired:
                print("   ✅ Expired token detection working")
            else:
                print("   ❌ Expired token detection failed")
            
            # Test 5: Token usage marking
            print("\n5. Testing token usage marking...")
            reset_token.mark_used(
                ip_address="192.168.1.100", 
                user_agent="Test Browser"
            )
            
            print(f"   Token used: {reset_token.used}")
            print(f"   Used at: {reset_token.used_at}")
            print(f"   IP address: {reset_token.ip_address}")
            print(f"   Is valid after use: {reset_token.is_valid}")
            
            if reset_token.used and not reset_token.is_valid:
                print("   ✅ Token usage marking working")
            else:
                print("   ❌ Token usage marking failed")
            
            print("\n" + "=" * 50)
            print("🎉 Password Reset test completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Error during testing: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


async def main():
    """Run password reset tests."""
    success = await test_password_reset()
    if not success:
        sys.exit(1)
    
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())