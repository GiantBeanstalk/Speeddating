"""
Notification Service

Handles various types of notifications and broadcasting.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Attendee, Event, Match, Round
from app.websocket.connection_manager import connection_manager


class NotificationType(str, Enum):
    """Types of notifications."""

    ROUND_STARTED = "round_started"
    ROUND_ENDED = "round_ended"
    BREAK_STARTED = "break_started"
    BREAK_ENDED = "break_ended"
    TIMER_WARNING = "timer_warning"
    MATCH_CREATED = "match_created"
    MATCH_RESPONSE = "match_response"
    MUTUAL_MATCH = "mutual_match"
    EVENT_STATUS_CHANGE = "event_status_change"
    PAYMENT_CONFIRMED = "payment_confirmed"
    CHECK_IN_STATUS = "check_in_status"
    ANNOUNCEMENT = "announcement"


class NotificationService:
    """Service for sending various types of notifications."""

    def __init__(self):
        pass

    async def send_round_notification(
        self,
        notification_type: NotificationType,
        round_obj: Round,
        session: AsyncSession,
        additional_data: dict[str, Any] | None = None,
    ):
        """Send a round-related notification to all event participants."""

        message = {
            "type": notification_type.value,
            "round_id": str(round_obj.id),
            "round_number": round_obj.round_number,
            "round_name": round_obj.name,
            "event_id": str(round_obj.event_id),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if additional_data:
            message.update(additional_data)

        # Customize message based on type
        if notification_type == NotificationType.ROUND_STARTED:
            message.update(
                {
                    "title": f"Round {round_obj.round_number} Started",
                    "message": f"{round_obj.name} has begun! Duration: {round_obj.duration_minutes} minutes",
                    "duration_minutes": round_obj.duration_minutes,
                }
            )

        elif notification_type == NotificationType.ROUND_ENDED:
            message.update(
                {
                    "title": f"Round {round_obj.round_number} Ended",
                    "message": f"{round_obj.name} has concluded",
                    "completion_percentage": round_obj.completion_percentage,
                }
            )

        elif notification_type == NotificationType.BREAK_STARTED:
            message.update(
                {
                    "title": "Break Time",
                    "message": f"Break period started for {round_obj.break_after_minutes} minutes",
                    "break_duration_minutes": round_obj.break_after_minutes,
                }
            )

        elif notification_type == NotificationType.BREAK_ENDED:
            message.update({"title": "Break Over", "message": "Break period has ended"})

        # Broadcast to all participants in the event
        await connection_manager.broadcast_to_event(message, round_obj.event_id)

    async def send_match_notification(
        self,
        notification_type: NotificationType,
        match: Match,
        session: AsyncSession,
        recipient_user_id: uuid.UUID | None = None,
    ):
        """Send a match-related notification."""

        # Get match details with attendees
        match_result = await session.execute(
            select(Match)
            .options(
                selectinload(Match.attendee1).selectinload(Attendee.user),
                selectinload(Match.attendee2).selectinload(Attendee.user),
                selectinload(Match.round),
                selectinload(Match.event),
            )
            .where(Match.id == match.id)
        )
        match_obj = match_result.scalar_one_or_none()

        if not match_obj:
            return

        message = {
            "type": notification_type.value,
            "match_id": str(match_obj.id),
            "event_id": str(match_obj.event_id),
            "round_id": str(match_obj.round_id) if match_obj.round_id else None,
            "round_number": match_obj.round.round_number if match_obj.round else None,
            "table_number": match_obj.table_number,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if notification_type == NotificationType.MATCH_CREATED:
            message.update(
                {
                    "title": "New Match",
                    "message": f"You have been matched for Round {match_obj.round.round_number if match_obj.round else 'TBD'}",
                    "table_number": match_obj.table_number,
                }
            )

            # Send to both attendees
            await connection_manager.send_to_user(message, match_obj.attendee1.user_id)
            await connection_manager.send_to_user(message, match_obj.attendee2.user_id)

        elif notification_type == NotificationType.MATCH_RESPONSE:
            # Determine who responded and who should be notified
            if recipient_user_id:
                message.update(
                    {
                        "title": "Match Response Received",
                        "message": "Your match has responded",
                        "is_mutual": match_obj.is_mutual_match,
                        "both_responded": match_obj.both_responded,
                    }
                )
                await connection_manager.send_to_user(message, recipient_user_id)

        elif notification_type == NotificationType.MUTUAL_MATCH:
            # Get contact info for mutual matches
            attendee1_contact = match_obj.attendee1.get_contact_info(is_matched=True)
            attendee2_contact = match_obj.attendee2.get_contact_info(is_matched=True)

            # Send to attendee1
            message_1 = message.copy()
            message_1.update(
                {
                    "title": "🎉 Mutual Match!",
                    "message": f"You and {match_obj.attendee2.display_name} both want to meet!",
                    "match_name": match_obj.attendee2.display_name,
                    "match_contact": attendee2_contact,
                }
            )
            await connection_manager.send_to_user(
                message_1, match_obj.attendee1.user_id
            )

            # Send to attendee2
            message_2 = message.copy()
            message_2.update(
                {
                    "title": "🎉 Mutual Match!",
                    "message": f"You and {match_obj.attendee1.display_name} both want to meet!",
                    "match_name": match_obj.attendee1.display_name,
                    "match_contact": attendee1_contact,
                }
            )
            await connection_manager.send_to_user(
                message_2, match_obj.attendee2.user_id
            )

    async def send_event_notification(
        self,
        notification_type: NotificationType,
        event: Event,
        message_text: str,
        title: str | None = None,
        session: AsyncSession = None,
    ):
        """Send an event-wide notification."""

        message = {
            "type": notification_type.value,
            "event_id": str(event.id),
            "title": title or "Event Update",
            "message": message_text,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if notification_type == NotificationType.EVENT_STATUS_CHANGE:
            message.update(
                {"event_status": event.status.value, "event_name": event.name}
            )

        await connection_manager.broadcast_to_event(message, event.id)

    async def send_personal_notification(
        self,
        user_id: uuid.UUID,
        notification_type: NotificationType,
        title: str,
        message_text: str,
        additional_data: dict[str, Any] | None = None,
    ):
        """Send a personal notification to a specific user."""

        message = {
            "type": notification_type.value,
            "title": title,
            "message": message_text,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if additional_data:
            message.update(additional_data)

        await connection_manager.send_to_user(message, user_id)

    async def send_payment_notification(
        self, attendee: Attendee, is_confirmed: bool, session: AsyncSession
    ):
        """Send payment confirmation notification."""

        if is_confirmed:
            await self.send_personal_notification(
                attendee.user_id,
                NotificationType.PAYMENT_CONFIRMED,
                "Payment Confirmed",
                f"Your payment for {attendee.event.name} has been confirmed. You're all set!",
                {
                    "event_id": str(attendee.event_id),
                    "attendee_id": str(attendee.id),
                    "payment_confirmed": True,
                },
            )
        else:
            await self.send_personal_notification(
                attendee.user_id,
                NotificationType.PAYMENT_CONFIRMED,
                "Payment Required",
                f"Payment is required for {attendee.event.name}. Please contact the organizer.",
                {
                    "event_id": str(attendee.event_id),
                    "attendee_id": str(attendee.id),
                    "payment_confirmed": False,
                },
            )

    async def send_check_in_notification(self, attendee: Attendee, is_checked_in: bool):
        """Send check-in status notification."""

        if is_checked_in:
            await self.send_personal_notification(
                attendee.user_id,
                NotificationType.CHECK_IN_STATUS,
                "Checked In Successfully",
                f"You have been checked in for {attendee.event.name}",
                {
                    "event_id": str(attendee.event_id),
                    "attendee_id": str(attendee.id),
                    "checked_in": True,
                    "table_number": attendee.table_number,
                },
            )
        else:
            await self.send_personal_notification(
                attendee.user_id,
                NotificationType.CHECK_IN_STATUS,
                "Checked Out",
                f"You have been checked out from {attendee.event.name}",
                {
                    "event_id": str(attendee.event_id),
                    "attendee_id": str(attendee.id),
                    "checked_in": False,
                },
            )

    async def send_announcement(
        self,
        event_id: uuid.UUID,
        title: str,
        message_text: str,
        priority: str = "normal",
        expires_at: datetime | None = None,
    ):
        """Send an announcement to all event participants."""

        message = {
            "type": NotificationType.ANNOUNCEMENT.value,
            "event_id": str(event_id),
            "title": title,
            "message": message_text,
            "priority": priority,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await connection_manager.broadcast_to_event(message, event_id)

    async def send_timer_warning(
        self,
        event_id: uuid.UUID,
        round_id: uuid.UUID,
        seconds_remaining: int,
        warning_type: str = "round",  # "round" or "break"
    ):
        """Send timer warning notification."""

        if warning_type == "round":
            title = "Round Ending Soon"
            if seconds_remaining == 120:
                message_text = "2 minutes remaining in this round"
            elif seconds_remaining == 60:
                message_text = "1 minute remaining in this round"
            elif seconds_remaining == 30:
                message_text = "30 seconds remaining in this round"
            elif seconds_remaining == 10:
                message_text = "10 seconds remaining in this round"
            else:
                message_text = f"{seconds_remaining} seconds remaining in this round"
        else:  # break
            title = "Break Ending Soon"
            if seconds_remaining == 60:
                message_text = "Break ends in 1 minute"
            elif seconds_remaining == 30:
                message_text = "Break ends in 30 seconds"
            elif seconds_remaining == 10:
                message_text = "Break ends in 10 seconds"
            else:
                message_text = f"Break ends in {seconds_remaining} seconds"

        message = {
            "type": NotificationType.TIMER_WARNING.value,
            "event_id": str(event_id),
            "round_id": str(round_id),
            "title": title,
            "message": message_text,
            "seconds_remaining": seconds_remaining,
            "warning_type": warning_type,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await connection_manager.broadcast_to_event(message, event_id)


# Global notification service instance
notification_service = NotificationService()
