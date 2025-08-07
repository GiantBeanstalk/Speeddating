"""
Super user registration and management functionality.

Provides secure one-time super user account creation using a generated secret key.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class SuperUserManager:
    """Manages super user registration and secret key functionality."""

    def __init__(self, secret_file_path: str = ".super_user_secret"):
        """Initialize with path to secret file."""
        self.secret_file_path = Path(secret_file_path)

    def generate_secret_key(self) -> str:
        """Generate a new super user secret key and save it to file."""
        # Generate a cryptographically secure random key
        secret = secrets.token_urlsafe(32)
        
        # Create timestamp for when key was generated
        generated_at = datetime.now(UTC).isoformat()
        
        # Hash the secret for storage (we'll compare hashes)
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        
        # Save to file
        with open(self.secret_file_path, "w") as f:
            f.write(f"{secret_hash}\n{generated_at}\n")
        
        # Set restrictive permissions (owner read/write only)
        self.secret_file_path.chmod(0o600)
        
        return secret

    def verify_secret_key(self, provided_secret: str) -> bool:
        """Verify the provided secret against stored hash."""
        if not self.secret_file_path.exists():
            return False
            
        try:
            with open(self.secret_file_path, "r") as f:
                lines = f.read().strip().split("\n")
                if len(lines) < 2:
                    return False
                    
                stored_hash = lines[0]
                
            # Hash the provided secret and compare
            provided_hash = hashlib.sha256(provided_secret.encode()).hexdigest()
            return secrets.compare_digest(stored_hash, provided_hash)
            
        except (FileNotFoundError, PermissionError, ValueError):
            return False

    def delete_secret_key(self) -> bool:
        """Delete the secret key file after successful super user creation."""
        try:
            if self.secret_file_path.exists():
                self.secret_file_path.unlink()
                return True
            return False
        except (FileNotFoundError, PermissionError):
            return False

    def secret_key_exists(self) -> bool:
        """Check if secret key file exists."""
        return self.secret_file_path.exists()

    async def super_user_exists(self, session: AsyncSession) -> bool:
        """Check if a super user account already exists in the database."""
        result = await session.execute(
            select(func.count(User.id)).where(User.is_superuser == True)  # noqa: E712
        )
        count = result.scalar() or 0
        return count > 0

    async def can_create_super_user(self, session: AsyncSession) -> bool:
        """Check if super user creation is allowed (no super user exists and secret key exists)."""
        return (
            not await self.super_user_exists(session) 
            and self.secret_key_exists()
        )


# Global instance
super_user_manager = SuperUserManager()


def generate_super_user_secret() -> str:
    """Generate a new super user secret key."""
    return super_user_manager.generate_secret_key()


def verify_super_user_secret(secret: str) -> bool:
    """Verify a super user secret key."""
    return super_user_manager.verify_secret_key(secret)


async def initialize_super_user_secret() -> Optional[str]:
    """Initialize super user secret if none exists and no super user exists."""
    # Only generate secret on first run
    if not super_user_manager.secret_key_exists():
        secret = generate_super_user_secret()
        print("=" * 60)
        print("🔑 SUPER USER SECRET GENERATED")
        print("=" * 60)
        print(f"Secret Key: {secret}")
        print("")
        print("⚠️  IMPORTANT SECURITY NOTICE:")
        print("• This key will only be shown ONCE")
        print("• Save it securely - you'll need it to create the first admin account")
        print("• The secret file is stored with restricted permissions")
        print("• This registration will be disabled after the first super user is created")
        print("• Access the super user registration at: /setup/super-user")
        print("=" * 60)
        return secret
    
    return None