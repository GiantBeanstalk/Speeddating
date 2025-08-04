"""
QR Code Service

Handles QR code generation, validation, and PDF badge creation for attendees.
"""
import uuid
import qrcode
import hashlib
import secrets
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional, Dict, Any, BinaryIO
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import QRLogin, Attendee, Event, User
from app.config import settings


class QRCodeService:
    """Service for QR code generation and management."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def generate_attendee_qr_token(
        self, 
        attendee_id: uuid.UUID, 
        expire_hours: int = 24,
        max_uses: int = 10
    ) -> QRLogin:
        """Generate a secure QR login token for an attendee."""
        
        # Get attendee with related data
        attendee_result = await self.session.execute(
            select(Attendee)
            .options(
                selectinload(Attendee.user),
                selectinload(Attendee.event)
            )
            .where(Attendee.id == attendee_id)
        )
        attendee = attendee_result.scalar_one_or_none()
        
        if not attendee:
            raise ValueError("Attendee not found")
        
        # Check if attendee already has an active QR token
        existing_token = await self._get_active_qr_token(attendee_id)
        if existing_token:
            # Revoke existing token before creating new one
            existing_token.revoke_token("Replaced with new token")
        
        # Create new QR login token
        qr_login = QRLogin.create_for_attendee(
            attendee_id=attendee_id,
            event_id=attendee.event_id,
            user_id=attendee.user_id,
            expire_hours=expire_hours
        )
        
        qr_login.max_uses = max_uses
        qr_login.qr_code_url = self._generate_qr_url(qr_login.token, attendee.event_id)
        
        self.session.add(qr_login)
        await self.session.commit()
        await self.session.refresh(qr_login)
        
        return qr_login
    
    async def _get_active_qr_token(self, attendee_id: uuid.UUID) -> Optional[QRLogin]:
        """Get the active QR token for an attendee."""
        result = await self.session.execute(
            select(QRLogin)
            .where(
                QRLogin.attendee_id == attendee_id,
                QRLogin.is_active == True,
                QRLogin.is_revoked == False,
                QRLogin.expires_at > datetime.utcnow()
            )
        )
        return result.scalar_one_or_none()
    
    def _generate_qr_url(self, token: str, event_id: uuid.UUID) -> str:
        """Generate the URL that will be embedded in the QR code."""
        base_url = settings.get("qr_code_base_url", "http://localhost:8000")
        return f"{base_url}/qr-login/{event_id}?token={token}"
    
    def create_qr_code_image(
        self, 
        qr_url: str, 
        size: int = 10,
        border: int = 4
    ) -> BytesIO:
        """Create a QR code image from a URL."""
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=size,
            border=border,
        )
        
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        return img_buffer
    
    async def validate_qr_token(
        self, 
        token: str, 
        event_id: uuid.UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Validate a QR token and return attendee information if valid."""
        
        # Hash the token for lookup
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Find the QR login record
        qr_result = await self.session.execute(
            select(QRLogin)
            .options(
                selectinload(QRLogin.attendee).selectinload(Attendee.user),
                selectinload(QRLogin.event)
            )
            .where(
                QRLogin.token_hash == token_hash,
                QRLogin.event_id == event_id
            )
        )
        qr_login = qr_result.scalar_one_or_none()
        
        if not qr_login:
            return None
        
        # Check if token is valid
        if not qr_login.is_valid:
            return None
        
        # Use the token (this will increment usage count)
        success = qr_login.use_token(ip_address=ip_address, user_agent=user_agent)
        
        if not success:
            return None
        
        # Save the usage
        await self.session.commit()
        
        # Return attendee and authentication information
        return {
            "attendee": qr_login.attendee,
            "event": qr_login.event,
            "user": qr_login.attendee.user,
            "qr_login": qr_login,
            "remaining_uses": qr_login.max_uses - qr_login.usage_count
        }
    
    async def revoke_attendee_qr_token(
        self, 
        attendee_id: uuid.UUID, 
        reason: str = "Manually revoked"
    ) -> bool:
        """Revoke an attendee's QR token."""
        
        qr_login = await self._get_active_qr_token(attendee_id)
        
        if qr_login:
            qr_login.revoke_token(reason)
            await self.session.commit()
            return True
        
        return False
    
    async def extend_qr_token_expiry(
        self, 
        attendee_id: uuid.UUID, 
        additional_hours: int = 24
    ) -> Optional[QRLogin]:
        """Extend the expiry time of an attendee's QR token."""
        
        qr_login = await self._get_active_qr_token(attendee_id)
        
        if qr_login:
            qr_login.extend_expiry(additional_hours)
            await self.session.commit()
            await self.session.refresh(qr_login)
            return qr_login
        
        return None
    
    async def get_qr_token_stats(self, event_id: uuid.UUID) -> Dict[str, Any]:
        """Get statistics about QR token usage for an event."""
        
        # Get all QR logins for the event
        qr_logins_result = await self.session.execute(
            select(QRLogin)
            .where(QRLogin.event_id == event_id)
        )
        qr_logins = list(qr_logins_result.scalars())
        
        if not qr_logins:
            return {
                "total_tokens": 0,
                "active_tokens": 0,
                "used_tokens": 0,
                "expired_tokens": 0,
                "revoked_tokens": 0,
                "total_usage_count": 0
            }
        
        # Calculate statistics
        now = datetime.utcnow()
        active_tokens = sum(1 for qr in qr_logins if qr.is_valid)
        used_tokens = sum(1 for qr in qr_logins if qr.usage_count > 0)
        expired_tokens = sum(1 for qr in qr_logins if qr.expires_at < now and not qr.is_revoked)
        revoked_tokens = sum(1 for qr in qr_logins if qr.is_revoked)
        total_usage = sum(qr.usage_count for qr in qr_logins)
        
        return {
            "total_tokens": len(qr_logins),
            "active_tokens": active_tokens,
            "used_tokens": used_tokens,
            "expired_tokens": expired_tokens,
            "revoked_tokens": revoked_tokens,
            "total_usage_count": total_usage
        }
    
    async def cleanup_expired_tokens(self, event_id: Optional[uuid.UUID] = None) -> int:
        """Clean up expired QR tokens. Returns number of tokens cleaned up."""
        
        from sqlalchemy import update
        
        # Build the query
        query = update(QRLogin).where(
            QRLogin.expires_at < datetime.utcnow(),
            QRLogin.is_revoked == False
        )
        
        if event_id:
            query = query.where(QRLogin.event_id == event_id)
        
        # Mark expired tokens as revoked
        result = await self.session.execute(
            query.values(
                is_revoked=True,
                revoked_at=datetime.utcnow(),
                revoked_reason="Automatically expired"
            )
        )
        
        await self.session.commit()
        return result.rowcount
    
    async def bulk_generate_qr_tokens(
        self, 
        event_id: uuid.UUID,
        expire_hours: int = 24,
        max_uses: int = 10
    ) -> List[QRLogin]:
        """Generate QR tokens for all attendees of an event."""
        
        # Get all confirmed attendees for the event
        attendees_result = await self.session.execute(
            select(Attendee)
            .where(
                Attendee.event_id == event_id,
                Attendee.registration_confirmed == True
            )
        )
        attendees = list(attendees_result.scalars())
        
        qr_tokens = []
        
        for attendee in attendees:
            try:
                qr_token = await self.generate_attendee_qr_token(
                    attendee.id, 
                    expire_hours=expire_hours,
                    max_uses=max_uses
                )
                qr_tokens.append(qr_token)
            except Exception as e:
                # Log error but continue with other attendees
                print(f"Failed to generate QR token for attendee {attendee.id}: {e}")
        
        return qr_tokens


async def create_qr_service(session: AsyncSession) -> QRCodeService:
    """Factory function to create a QRCodeService instance."""
    return QRCodeService(session)