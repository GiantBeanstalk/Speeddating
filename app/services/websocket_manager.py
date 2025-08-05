"""
WebSocket manager for real-time communication.

Handles WebSocket connections for real-time round timers, match updates,
and event notifications.
"""
import uuid
import json
import asyncio
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class ConnectionManager:
    """Manages WebSocket connections for real-time features."""
    
    def __init__(self):
        # Active connections by connection ID
        self.active_connections: Dict[str, WebSocket] = {}
        
        # User connections mapping
        self.user_connections: Dict[uuid.UUID, Set[str]] = {}
        
        # Event room subscriptions (event_id -> set of connection_ids)
        self.event_rooms: Dict[uuid.UUID, Set[str]] = {}
        
        # Round timer subscriptions (round_id -> set of connection_ids)
        self.round_timers: Dict[uuid.UUID, Set[str]] = {}
        
        # Connection metadata
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(
        self, 
        websocket: WebSocket, 
        connection_id: str,
        user: User,
        room_type: str = "general",
        room_id: Optional[uuid.UUID] = None
    ):
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        
        # Store connection
        self.active_connections[connection_id] = websocket
        
        # Track user connections
        if user.id not in self.user_connections:
            self.user_connections[user.id] = set()
        self.user_connections[user.id].add(connection_id)
        
        # Store connection metadata
        self.connection_metadata[connection_id] = {
            "user_id": user.id,
            "user_email": user.email,
            "is_organizer": user.is_organizer,
            "room_type": room_type,
            "room_id": room_id,
            "connected_at": datetime.utcnow()
        }
        
        # Subscribe to appropriate room
        if room_type == "event" and room_id:
            await self.join_event_room(connection_id, room_id)
        elif room_type == "round_timer" and room_id:
            await self.join_round_timer(connection_id, room_id)
        
        print(f"WebSocket connection {connection_id} established for user {user.email}")
    
    def disconnect(self, connection_id: str):
        """Remove a WebSocket connection."""
        if connection_id not in self.active_connections:
            return
        
        # Get connection metadata
        metadata = self.connection_metadata.get(connection_id, {})
        user_id = metadata.get("user_id")
        room_type = metadata.get("room_type")
        room_id = metadata.get("room_id")
        
        # Remove from user connections
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # Remove from rooms
        if room_type == "event" and room_id:
            self.leave_event_room(connection_id, room_id)
        elif room_type == "round_timer" and room_id:
            self.leave_round_timer(connection_id, room_id)
        
        # Clean up
        del self.active_connections[connection_id]
        if connection_id in self.connection_metadata:
            del self.connection_metadata[connection_id]
        
        print(f"WebSocket connection {connection_id} disconnected")
    
    async def join_event_room(self, connection_id: str, event_id: uuid.UUID):
        """Add connection to event room."""
        if event_id not in self.event_rooms:
            self.event_rooms[event_id] = set()
        self.event_rooms[event_id].add(connection_id)
        
        # Update metadata
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["room_id"] = event_id
    
    def leave_event_room(self, connection_id: str, event_id: uuid.UUID):
        """Remove connection from event room."""
        if event_id in self.event_rooms:
            self.event_rooms[event_id].discard(connection_id)
            if not self.event_rooms[event_id]:
                del self.event_rooms[event_id]
    
    async def join_round_timer(self, connection_id: str, round_id: uuid.UUID):
        """Add connection to round timer."""
        if round_id not in self.round_timers:
            self.round_timers[round_id] = set()
        self.round_timers[round_id].add(connection_id)
        
        # Update metadata
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["room_id"] = round_id
    
    def leave_round_timer(self, connection_id: str, round_id: uuid.UUID):
        """Remove connection from round timer."""
        if round_id in self.round_timers:
            self.round_timers[round_id].discard(connection_id)
            if not self.round_timers[round_id]:
                del self.round_timers[round_id]
    
    async def send_personal_message(self, message: dict, connection_id: str):
        """Send a message to a specific connection."""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending message to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    async def send_to_user(self, message: dict, user_id: uuid.UUID):
        """Send a message to all connections of a specific user."""
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id].copy():
                await self.send_personal_message(message, connection_id)
    
    async def broadcast_to_event(self, message: dict, event_id: uuid.UUID):
        """Broadcast a message to all connections in an event room."""
        if event_id in self.event_rooms:
            for connection_id in self.event_rooms[event_id].copy():
                await self.send_personal_message(message, connection_id)
    
    async def broadcast_to_round_timer(self, message: dict, round_id: uuid.UUID):
        """Broadcast timer updates to all connections watching a round."""
        if round_id in self.round_timers:
            for connection_id in self.round_timers[round_id].copy():
                await self.send_personal_message(message, connection_id)
    
    async def broadcast_to_organizers(self, message: dict, event_id: Optional[uuid.UUID] = None):
        """Broadcast a message to all organizer connections."""
        for connection_id, metadata in self.connection_metadata.items():
            if metadata.get("is_organizer"):
                # If event_id specified, only send to organizers in that event room
                if event_id is None or metadata.get("room_id") == event_id:
                    await self.send_personal_message(message, connection_id)
    
    def get_connection_stats(self) -> dict:
        """Get statistics about active connections."""
        return {
            "total_connections": len(self.active_connections),
            "unique_users": len(self.user_connections),
            "event_rooms": {str(k): len(v) for k, v in self.event_rooms.items()},
            "round_timers": {str(k): len(v) for k, v in self.round_timers.items()},
            "organizer_connections": len([
                c for c in self.connection_metadata.values() 
                if c.get("is_organizer")
            ])
        }


class RoundTimerManager:
    """Manages real-time round timers with automatic transitions."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.active_timers: Dict[uuid.UUID, asyncio.Task] = {}
        self.timer_data: Dict[uuid.UUID, Dict[str, Any]] = {}
    
    async def start_round_timer(
        self, 
        round_id: uuid.UUID, 
        duration_minutes: int,
        break_minutes: int = 0,
        session: Optional[AsyncSession] = None
    ):
        """Start a real-time timer for a round."""
        
        # Cancel existing timer if any
        await self.stop_round_timer(round_id)
        
        # Store timer data
        self.timer_data[round_id] = {
            "round_id": round_id,
            "duration_seconds": duration_minutes * 60,
            "break_seconds": break_minutes * 60,
            "started_at": datetime.utcnow(),
            "status": "active",
            "phase": "round"  # "round" or "break"
        }
        
        # Start timer task
        self.active_timers[round_id] = asyncio.create_task(
            self._run_round_timer(round_id, session)
        )
        
        print(f"Started timer for round {round_id} ({duration_minutes}m + {break_minutes}m break)")
    
    async def stop_round_timer(self, round_id: uuid.UUID):
        """Stop a round timer."""
        if round_id in self.active_timers:
            self.active_timers[round_id].cancel()
            del self.active_timers[round_id]
        
        if round_id in self.timer_data:
            del self.timer_data[round_id]
        
        print(f"Stopped timer for round {round_id}")
    
    async def _run_round_timer(self, round_id: uuid.UUID, session: Optional[AsyncSession] = None):
        """Run the actual timer loop for a round."""
        try:
            timer_data = self.timer_data[round_id]
            duration_seconds = timer_data["duration_seconds"]
            break_seconds = timer_data["break_seconds"]
            started_at = timer_data["started_at"]
            
            # Round phase
            for remaining in range(duration_seconds, -1, -1):
                if round_id not in self.timer_data:  # Timer was stopped
                    return
                
                # Calculate actual remaining time based on start time
                elapsed = (datetime.utcnow() - started_at).total_seconds()
                actual_remaining = max(0, duration_seconds - elapsed)
                
                # Broadcast timer update
                await self.connection_manager.broadcast_to_round_timer({
                    "type": "timer_update",
                    "round_id": str(round_id),
                    "phase": "round",
                    "time_remaining": int(actual_remaining),
                    "total_duration": duration_seconds,
                    "status": "active",
                    "percentage_complete": (elapsed / duration_seconds) * 100 if duration_seconds > 0 else 100
                }, round_id)
                
                # Send warnings at specific intervals
                if actual_remaining <= 60 and actual_remaining > 50:
                    await self.connection_manager.broadcast_to_round_timer({
                        "type": "timer_warning",
                        "round_id": str(round_id),
                        "message": "1 minute remaining",
                        "warning_type": "one_minute"
                    }, round_id)
                elif actual_remaining <= 30 and actual_remaining > 20:
                    await self.connection_manager.broadcast_to_round_timer({
                        "type": "timer_warning",
                        "round_id": str(round_id),
                        "message": "30 seconds remaining",
                        "warning_type": "thirty_seconds"
                    }, round_id)
                elif actual_remaining <= 10 and actual_remaining > 0:
                    await self.connection_manager.broadcast_to_round_timer({
                        "type": "timer_warning",
                        "round_id": str(round_id),
                        "message": f"{int(actual_remaining)} seconds remaining",
                        "warning_type": "countdown"
                    }, round_id)
                
                if actual_remaining <= 0:
                    break
                
                await asyncio.sleep(1)
            
            # Round ended
            await self.connection_manager.broadcast_to_round_timer({
                "type": "round_ended",
                "round_id": str(round_id),
                "message": "Round completed! Please finish your conversations."
            }, round_id)
            
            # Break phase (if configured)
            if break_seconds > 0:
                self.timer_data[round_id]["phase"] = "break"
                break_start = datetime.utcnow()
                
                await self.connection_manager.broadcast_to_round_timer({
                    "type": "break_started",
                    "round_id": str(round_id),
                    "break_duration": break_seconds,
                    "message": f"Break time! {break_seconds // 60} minutes until next round."
                }, round_id)
                
                for remaining in range(break_seconds, -1, -1):
                    if round_id not in self.timer_data:  # Timer was stopped
                        return
                    
                    # Calculate actual remaining break time
                    break_elapsed = (datetime.utcnow() - break_start).total_seconds()
                    actual_remaining = max(0, break_seconds - break_elapsed)
                    
                    # Broadcast break timer update
                    await self.connection_manager.broadcast_to_round_timer({
                        "type": "timer_update",
                        "round_id": str(round_id),
                        "phase": "break",
                        "time_remaining": int(actual_remaining),
                        "total_duration": break_seconds,
                        "status": "break",
                        "percentage_complete": (break_elapsed / break_seconds) * 100 if break_seconds > 0 else 100
                    }, round_id)
                    
                    # Break warnings
                    if actual_remaining <= 60 and actual_remaining > 50:
                        await self.connection_manager.broadcast_to_round_timer({
                            "type": "timer_warning",
                            "round_id": str(round_id),
                            "message": "Break ends in 1 minute",
                            "warning_type": "break_ending_soon"
                        }, round_id)
                    elif actual_remaining <= 30 and actual_remaining > 20:
                        await self.connection_manager.broadcast_to_round_timer({
                            "type": "timer_warning",
                            "round_id": str(round_id),
                            "message": "Break ends in 30 seconds",
                            "warning_type": "break_ending_very_soon"
                        }, round_id)
                    
                    if actual_remaining <= 0:
                        break
                    
                    await asyncio.sleep(1)
                
                # Break ended
                await self.connection_manager.broadcast_to_round_timer({
                    "type": "break_ended",
                    "round_id": str(round_id),
                    "message": "Break time is over! Next round will begin shortly."
                }, round_id)
            
            # Timer completed
            if round_id in self.timer_data:
                self.timer_data[round_id]["status"] = "completed"
            
        except asyncio.CancelledError:
            print(f"Timer for round {round_id} was cancelled")
        except Exception as e:
            print(f"Error in round timer {round_id}: {e}")
            await self.connection_manager.broadcast_to_round_timer({
                "type": "timer_error",
                "round_id": str(round_id),
                "message": "Timer error occurred",
                "error": str(e)
            }, round_id)
        finally:
            # Clean up
            if round_id in self.active_timers:
                del self.active_timers[round_id]
            if round_id in self.timer_data:
                del self.timer_data[round_id]
    
    def get_timer_status(self, round_id: uuid.UUID) -> Optional[dict]:
        """Get current status of a round timer."""
        if round_id not in self.timer_data:
            return None
        
        timer_data = self.timer_data[round_id]
        started_at = timer_data["started_at"]
        elapsed = (datetime.utcnow() - started_at).total_seconds()
        
        if timer_data["phase"] == "round":
            remaining = max(0, timer_data["duration_seconds"] - elapsed)
        else:  # break
            break_start_offset = timer_data["duration_seconds"]
            break_elapsed = max(0, elapsed - break_start_offset)
            remaining = max(0, timer_data["break_seconds"] - break_elapsed)
        
        return {
            "round_id": str(round_id),
            "phase": timer_data["phase"],
            "status": timer_data["status"],
            "time_remaining": int(remaining),
            "elapsed_time": int(elapsed),
            "started_at": started_at.isoformat()
        }
    
    def get_all_active_timers(self) -> List[dict]:
        """Get status of all active timers."""
        return [
            self.get_timer_status(round_id) 
            for round_id in self.active_timers.keys()
        ]


class EventCountdownManager:
    """Manages real-time event countdown timers."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.active_countdowns: Dict[uuid.UUID, asyncio.Task] = {}
        self.countdown_data: Dict[uuid.UUID, Dict[str, Any]] = {}
    
    async def start_event_countdown(
        self,
        event_id: uuid.UUID,
        duration_minutes: int,
        message: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ):
        """Start a real-time countdown for an event."""
        
        # Cancel existing countdown if any
        await self.stop_event_countdown(event_id)
        
        # Store countdown data
        now = datetime.utcnow()
        target_time = now + timedelta(minutes=duration_minutes)
        
        self.countdown_data[event_id] = {
            "event_id": event_id,
            "duration_seconds": duration_minutes * 60,
            "started_at": now,
            "target_time": target_time,
            "message": message or f"Event starts in {duration_minutes} minutes!",
            "status": "active"
        }
        
        # Start countdown task
        self.active_countdowns[event_id] = asyncio.create_task(
            self._run_event_countdown(event_id, session)
        )
        
        print(f"Started countdown for event {event_id} ({duration_minutes} minutes)")
    
    async def stop_event_countdown(self, event_id: uuid.UUID):
        """Stop an event countdown."""
        if event_id in self.active_countdowns:
            self.active_countdowns[event_id].cancel()
            del self.active_countdowns[event_id]
        
        if event_id in self.countdown_data:
            del self.countdown_data[event_id]
        
        print(f"Stopped countdown for event {event_id}")
    
    async def extend_event_countdown(self, event_id: uuid.UUID, additional_minutes: int):
        """Extend an active countdown."""
        if event_id not in self.countdown_data:
            raise ValueError("No active countdown for this event")
        
        countdown_data = self.countdown_data[event_id]
        new_target = countdown_data["target_time"] + timedelta(minutes=additional_minutes)
        countdown_data["target_time"] = new_target
        countdown_data["duration_seconds"] += additional_minutes * 60
        
        # Broadcast extension notification
        await self.connection_manager.broadcast_to_event({
            "type": "countdown_extended",
            "event_id": str(event_id),
            "additional_minutes": additional_minutes,
            "new_target_time": new_target.isoformat(),
            "message": f"Countdown extended by {additional_minutes} minutes!"
        }, event_id)
    
    async def _run_event_countdown(self, event_id: uuid.UUID, session: Optional[AsyncSession] = None):
        """Run the actual countdown loop for an event."""
        try:
            countdown_data = self.countdown_data[event_id]
            started_at = countdown_data["started_at"]
            target_time = countdown_data["target_time"]
            total_seconds = countdown_data["duration_seconds"]
            message = countdown_data["message"]
            
            # Track warnings sent to avoid duplicates
            warnings_sent = set()
            
            while True:
                if event_id not in self.countdown_data:  # Countdown was stopped
                    return
                
                now = datetime.utcnow()
                remaining_seconds = max(0, int((target_time - now).total_seconds()))
                elapsed_seconds = int((now - started_at).total_seconds())
                percentage = (elapsed_seconds / total_seconds * 100) if total_seconds > 0 else 0
                
                # Check if countdown is complete
                if remaining_seconds <= 0:
                    # Countdown completed
                    await self.connection_manager.broadcast_to_event({
                        "type": "countdown_completed",
                        "event_id": str(event_id),
                        "message": "🎯 Event is starting now! Get ready for the first round.",
                        "completed_at": now.isoformat()
                    }, event_id)
                    
                    # Mark as completed and exit
                    if event_id in self.countdown_data:
                        self.countdown_data[event_id]["status"] = "completed"
                    break
                
                # Broadcast countdown update every second
                await self.connection_manager.broadcast_to_event({
                    "type": "countdown_update",
                    "event_id": str(event_id),
                    "time_remaining": remaining_seconds,
                    "total_duration": total_seconds,
                    "percentage_complete": min(100, max(0, percentage)),
                    "message": message,
                    "target_time": target_time.isoformat()
                }, event_id)
                
                # Send warnings at specific intervals
                minutes_remaining = remaining_seconds // 60
                
                if remaining_seconds <= 600 and "10min" not in warnings_sent and minutes_remaining >= 9:  # 10 minutes
                    warnings_sent.add("10min")
                    await self.connection_manager.broadcast_to_event({
                        "type": "countdown_warning",
                        "event_id": str(event_id),
                        "message": "⏰ 10 minutes until event starts!",
                        "warning_type": "ten_minutes",
                        "time_remaining": remaining_seconds
                    }, event_id)
                
                elif remaining_seconds <= 300 and "5min" not in warnings_sent and minutes_remaining >= 4:  # 5 minutes
                    warnings_sent.add("5min")
                    await self.connection_manager.broadcast_to_event({
                        "type": "countdown_warning",
                        "event_id": str(event_id),
                        "message": "⚠️ 5 minutes until event starts! Please take your seats.",
                        "warning_type": "five_minutes",
                        "time_remaining": remaining_seconds
                    }, event_id)
                
                elif remaining_seconds <= 120 and "2min" not in warnings_sent and minutes_remaining >= 1:  # 2 minutes
                    warnings_sent.add("2min")
                    await self.connection_manager.broadcast_to_event({
                        "type": "countdown_warning",
                        "event_id": str(event_id),
                        "message": "🚨 2 minutes until event starts!",
                        "warning_type": "two_minutes",
                        "time_remaining": remaining_seconds
                    }, event_id)
                
                elif remaining_seconds <= 60 and "1min" not in warnings_sent:  # 1 minute
                    warnings_sent.add("1min")
                    await self.connection_manager.broadcast_to_event({
                        "type": "countdown_warning",
                        "event_id": str(event_id),
                        "message": "🔥 1 minute until event starts!",
                        "warning_type": "one_minute",
                        "time_remaining": remaining_seconds
                    }, event_id)
                
                elif remaining_seconds <= 30 and "30sec" not in warnings_sent:  # 30 seconds
                    warnings_sent.add("30sec")
                    await self.connection_manager.broadcast_to_event({
                        "type": "countdown_warning",
                        "event_id": str(event_id),
                        "message": "⚡ 30 seconds until event starts!",
                        "warning_type": "thirty_seconds",
                        "time_remaining": remaining_seconds
                    }, event_id)
                
                elif remaining_seconds <= 10 and "10sec" not in warnings_sent:  # 10 seconds
                    warnings_sent.add("10sec")
                    await self.connection_manager.broadcast_to_event({
                        "type": "countdown_warning",
                        "event_id": str(event_id),
                        "message": f"🎯 {remaining_seconds} seconds!",
                        "warning_type": "final_countdown",
                        "time_remaining": remaining_seconds
                    }, event_id)
                
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            print(f"Countdown for event {event_id} was cancelled")
        except Exception as e:
            print(f"Error in event countdown {event_id}: {e}")
        finally:
            # Clean up
            if event_id in self.active_countdowns:
                del self.active_countdowns[event_id]
            if event_id in self.countdown_data:
                del self.countdown_data[event_id]
    
    def get_countdown_status(self, event_id: uuid.UUID) -> Optional[dict]:
        """Get current status of an event countdown."""
        if event_id not in self.countdown_data:
            return None
        
        countdown_data = self.countdown_data[event_id]
        now = datetime.utcnow()
        target_time = countdown_data["target_time"]
        started_at = countdown_data["started_at"]
        
        remaining_seconds = max(0, int((target_time - now).total_seconds()))
        elapsed_seconds = int((now - started_at).total_seconds())
        total_seconds = countdown_data["duration_seconds"]
        percentage = (elapsed_seconds / total_seconds * 100) if total_seconds > 0 else 0
        
        return {
            "event_id": str(event_id),
            "active": remaining_seconds > 0,
            "time_remaining": remaining_seconds,
            "total_duration": total_seconds,
            "percentage_complete": min(100, max(0, percentage)),
            "message": countdown_data["message"],
            "target_time": target_time.isoformat(),
            "started_at": started_at.isoformat()
        }
    
    def get_all_active_countdowns(self) -> List[dict]:
        """Get status of all active countdowns."""
        return [
            self.get_countdown_status(event_id)
            for event_id in self.active_countdowns.keys()
        ]


# Global instances
connection_manager = ConnectionManager()
timer_manager = RoundTimerManager(connection_manager)
countdown_manager = EventCountdownManager(connection_manager)