"""
Round Timer WebSocket Endpoint

Handles real-time round timer updates and notifications.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models import Event, Round, RoundStatus

from .connection_manager import connection_manager

logger = logging.getLogger(__name__)


class RoundTimerHandler:
    """Handles round timer WebSocket connections and updates."""

    def __init__(self):
        # Active round timers: {round_id: timer_task}
        self.active_timers: dict[uuid.UUID, asyncio.Task] = {}

        # Round timer state: {round_id: timer_state}
        self.timer_states: dict[uuid.UUID, dict[str, Any]] = {}

    async def handle_connection(
        self,
        websocket: WebSocket,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        session: AsyncSession,
    ):
        """Handle a new WebSocket connection for round timer updates."""

        # Verify user has access to the event
        event_result = await session.execute(select(Event).where(Event.id == event_id))
        event = event_result.scalar_one_or_none()

        if not event:
            await websocket.close(code=1008, reason="Event not found")
            return

        # Check if user is organizer or attendee
        if event.organizer_id != user_id:
            # Check if user is an attendee
            from app.models import Attendee

            attendee_result = await session.execute(
                select(Attendee).where(
                    Attendee.event_id == event_id, Attendee.user_id == user_id
                )
            )
            attendee = attendee_result.scalar_one_or_none()

            if not attendee:
                await websocket.close(code=1008, reason="Access denied")
                return

        # Register connection
        connection_id = await connection_manager.connect(
            websocket, user_id, event_id, "round_timer"
        )

        try:
            # Send current timer state for all rounds in the event
            await self.send_current_timer_state(event_id, connection_id, session)

            # Handle incoming messages
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await self.handle_message(
                        message, connection_id, event_id, user_id, session
                    )

                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError:
                    await connection_manager.send_personal_message(
                        {"type": "error", "message": "Invalid JSON format"},
                        connection_id,
                    )
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    await connection_manager.send_personal_message(
                        {"type": "error", "message": "Internal server error"},
                        connection_id,
                    )

        except WebSocketDisconnect:
            pass
        finally:
            await connection_manager.disconnect(connection_id)

    async def handle_message(
        self,
        message: dict[str, Any],
        connection_id: str,
        event_id: uuid.UUID,
        user_id: uuid.UUID,
        session: AsyncSession,
    ):
        """Handle incoming WebSocket messages."""

        message_type = message.get("type")

        if message_type == "heartbeat":
            await connection_manager.handle_heartbeat(connection_id)

        elif message_type == "subscribe_round":
            round_id = message.get("round_id")
            if round_id:
                await self.subscribe_to_round(
                    uuid.UUID(round_id), connection_id, session
                )

        elif message_type == "request_timer_update":
            round_id = message.get("round_id")
            if round_id:
                await self.send_round_timer_update(
                    uuid.UUID(round_id), connection_id, session
                )

        else:
            await connection_manager.send_personal_message(
                {"type": "error", "message": f"Unknown message type: {message_type}"},
                connection_id,
            )

    async def send_current_timer_state(
        self, event_id: uuid.UUID, connection_id: str, session: AsyncSession
    ):
        """Send current timer state for all rounds in an event."""

        # Get all rounds for the event
        rounds_result = await session.execute(
            select(Round).where(Round.event_id == event_id).order_by(Round.round_number)
        )
        rounds = rounds_result.scalars().all()

        timer_states = []
        for round_obj in rounds:
            timer_state = await self.calculate_timer_state(round_obj)
            timer_states.append(timer_state)

        await connection_manager.send_personal_message(
            {
                "type": "timer_state_batch",
                "event_id": str(event_id),
                "rounds": timer_states,
                "timestamp": datetime.utcnow().isoformat(),
            },
            connection_id,
        )

    async def calculate_timer_state(self, round_obj: Round) -> dict[str, Any]:
        """Calculate current timer state for a round."""
        now = datetime.utcnow()

        timer_state = {
            "round_id": str(round_obj.id),
            "round_number": round_obj.round_number,
            "name": round_obj.name,
            "status": round_obj.status.value,
            "duration_minutes": round_obj.duration_minutes,
            "break_after_minutes": round_obj.break_after_minutes,
            "time_remaining": None,
            "break_time_remaining": None,
            "total_elapsed": 0,
            "is_break_active": round_obj.is_break_active,
            "scheduled_start": round_obj.scheduled_start.isoformat()
            if round_obj.scheduled_start
            else None,
            "actual_start": round_obj.actual_start.isoformat()
            if round_obj.actual_start
            else None,
            "completion_percentage": round_obj.completion_percentage,
        }

        if round_obj.status == RoundStatus.PENDING:
            return timer_state

        if not round_obj.actual_start:
            return timer_state

        elapsed = (now - round_obj.actual_start).total_seconds()
        round_duration_seconds = round_obj.duration_minutes * 60
        break_duration_seconds = round_obj.break_after_minutes * 60

        timer_state["total_elapsed"] = int(elapsed)

        if round_obj.status == RoundStatus.ACTIVE:
            time_remaining = max(0, round_duration_seconds - elapsed)
            timer_state["time_remaining"] = int(time_remaining)

        elif round_obj.status == RoundStatus.BREAK:
            # Calculate break time remaining
            break_start = round_obj.actual_start + timedelta(
                seconds=round_duration_seconds
            )
            break_elapsed = (now - break_start).total_seconds()
            break_time_remaining = max(0, break_duration_seconds - break_elapsed)

            timer_state["time_remaining"] = 0
            timer_state["break_time_remaining"] = int(break_time_remaining)

        return timer_state

    async def subscribe_to_round(
        self, round_id: uuid.UUID, connection_id: str, session: AsyncSession
    ):
        """Subscribe a connection to timer updates for a specific round."""

        round_result = await session.execute(select(Round).where(Round.id == round_id))
        round_obj = round_result.scalar_one_or_none()

        if not round_obj:
            await connection_manager.send_personal_message(
                {"type": "error", "message": "Round not found"}, connection_id
            )
            return

        # Send current timer state
        await self.send_round_timer_update(round_id, connection_id, session)

        await connection_manager.send_personal_message(
            {
                "type": "subscription_confirmed",
                "round_id": str(round_id),
                "message": f"Subscribed to timer updates for {round_obj.name}",
            },
            connection_id,
        )

    async def send_round_timer_update(
        self, round_id: uuid.UUID, connection_id: str, session: AsyncSession
    ):
        """Send timer update for a specific round."""

        round_result = await session.execute(select(Round).where(Round.id == round_id))
        round_obj = round_result.scalar_one_or_none()

        if not round_obj:
            return

        timer_state = await self.calculate_timer_state(round_obj)

        await connection_manager.send_personal_message(
            {
                "type": "timer_update",
                "round": timer_state,
                "timestamp": datetime.utcnow().isoformat(),
            },
            connection_id,
        )

    async def broadcast_round_update(
        self,
        round_id: uuid.UUID,
        event_id: uuid.UUID,
        session: AsyncSession,
        message_type: str = "timer_update",
    ):
        """Broadcast timer update to all connections watching an event."""

        round_result = await session.execute(select(Round).where(Round.id == round_id))
        round_obj = round_result.scalar_one_or_none()

        if not round_obj:
            return

        timer_state = await self.calculate_timer_state(round_obj)

        await connection_manager.broadcast_to_event(
            {
                "type": message_type,
                "round": timer_state,
                "timestamp": datetime.utcnow().isoformat(),
            },
            event_id,
        )

    async def start_round_timer(
        self, round_id: uuid.UUID, event_id: uuid.UUID, session: AsyncSession
    ):
        """Start an automatic timer for a round."""

        if round_id in self.active_timers:
            # Cancel existing timer
            self.active_timers[round_id].cancel()

        # Create new timer task
        timer_task = asyncio.create_task(
            self._round_timer_task(round_id, event_id, session)
        )
        self.active_timers[round_id] = timer_task

        logger.info(f"Started timer for round {round_id}")

    async def stop_round_timer(self, round_id: uuid.UUID):
        """Stop automatic timer for a round."""

        if round_id in self.active_timers:
            self.active_timers[round_id].cancel()
            del self.active_timers[round_id]
            logger.info(f"Stopped timer for round {round_id}")

    async def _round_timer_task(
        self, round_id: uuid.UUID, event_id: uuid.UUID, session: AsyncSession
    ):
        """Background task that manages automatic round timing."""

        try:
            # Get round details
            round_result = await session.execute(
                select(Round).where(Round.id == round_id)
            )
            round_obj = round_result.scalar_one_or_none()

            if not round_obj or round_obj.status != RoundStatus.ACTIVE:
                return

            duration_seconds = round_obj.duration_minutes * 60
            break_seconds = round_obj.break_after_minutes * 60

            # Send periodic updates during round
            update_interval = 5  # Update every 5 seconds
            updates_sent = 0

            while updates_sent * update_interval < duration_seconds:
                await asyncio.sleep(update_interval)
                updates_sent += 1

                # Send timer update
                await self.broadcast_round_update(round_id, event_id, session)

                # Send warnings at specific intervals
                remaining = duration_seconds - (updates_sent * update_interval)
                if remaining in [
                    120,
                    60,
                    30,
                    10,
                ]:  # 2 min, 1 min, 30 sec, 10 sec warnings
                    await connection_manager.broadcast_to_event(
                        {
                            "type": "timer_warning",
                            "round_id": str(round_id),
                            "seconds_remaining": remaining,
                            "message": f"{remaining} seconds remaining in round",
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        event_id,
                    )

            # Round time is up - start break if configured
            if break_seconds > 0:
                # Update round to break status
                round_obj.start_break()
                await session.commit()

                await connection_manager.broadcast_to_event(
                    {
                        "type": "round_break_started",
                        "round_id": str(round_id),
                        "break_duration_minutes": round_obj.break_after_minutes,
                        "message": f"Break started for {round_obj.break_after_minutes} minutes",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    event_id,
                )

                # Timer for break period
                break_updates = 0
                while break_updates * update_interval < break_seconds:
                    await asyncio.sleep(update_interval)
                    break_updates += 1

                    await self.broadcast_round_update(round_id, event_id, session)

                    # Break warnings
                    remaining = break_seconds - (break_updates * update_interval)
                    if remaining in [60, 30, 10]:  # 1 min, 30 sec, 10 sec warnings
                        await connection_manager.broadcast_to_event(
                            {
                                "type": "break_warning",
                                "round_id": str(round_id),
                                "seconds_remaining": remaining,
                                "message": f"Break ends in {remaining} seconds",
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                            event_id,
                        )

            # End the round
            round_obj.end_round()
            await session.commit()

            await connection_manager.broadcast_to_event(
                {
                    "type": "round_ended",
                    "round_id": str(round_id),
                    "message": f"Round {round_obj.round_number} has ended",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                event_id,
            )

            # Final timer update
            await self.broadcast_round_update(
                round_id, event_id, session, "round_completed"
            )

        except asyncio.CancelledError:
            logger.info(f"Timer cancelled for round {round_id}")
        except Exception as e:
            logger.error(f"Error in round timer task for {round_id}: {e}")
        finally:
            # Clean up
            if round_id in self.active_timers:
                del self.active_timers[round_id]


# Global round timer handler instance
round_timer_handler = RoundTimerHandler()


async def round_timer_websocket(
    websocket: WebSocket,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """WebSocket endpoint for round timer updates."""
    await round_timer_handler.handle_connection(websocket, event_id, user_id, session)
