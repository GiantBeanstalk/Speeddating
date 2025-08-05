"""
WebSocket endpoints for real-time features.

Provides WebSocket connections for real-time round timers, match updates,
and event notifications.
"""
import uuid
import json
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session  
from app.models import User, Event, Round
from app.auth import get_current_user_websocket
from app.services.websocket_manager import connection_manager, timer_manager


router = APIRouter()


@router.websocket("/ws/event/{event_id}")
async def websocket_event_room(
    websocket: WebSocket,
    event_id: uuid.UUID,
    token: str,
    session: AsyncSession = Depends(get_async_session)
):
    """WebSocket endpoint for event-wide real-time updates."""
    
    try:
        # Authenticate user
        user = await get_current_user_websocket(token, session)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Verify access to event
        from sqlalchemy import select, and_
        if user.is_organizer:
            # Organizers can access events they own
            event_result = await session.execute(
                select(Event).where(
                    and_(Event.id == event_id, Event.organizer_id == user.id)
                )
            )
        else:
            # Regular users can access events they're attending
            from app.models import Attendee
            event_result = await session.execute(
                select(Event)
                .join(Attendee, Attendee.event_id == Event.id)
                .where(
                    and_(Event.id == event_id, Attendee.user_id == user.id)
                )
            )
        
        event = event_result.scalar_one_or_none()
        if not event:
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return
        
        # Generate connection ID and connect
        connection_id = str(uuid.uuid4())
        await connection_manager.connect(
            websocket, 
            connection_id, 
            user,
            room_type="event",
            room_id=event_id
        )
        
        # Send welcome message with countdown status
        from app.services.websocket_manager import countdown_manager
        countdown_status = countdown_manager.get_countdown_status(event_id)
        
        await connection_manager.send_personal_message({
            "type": "connected",
            "message": f"Connected to event: {event.name}",
            "event_id": str(event_id),
            "user_role": "organizer" if user.is_organizer else "attendee",
            "countdown_status": countdown_status
        }, connection_id)
        
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                message = json.loads(data)
                message_type = message.get("type")
                
                # Handle different message types
                if message_type == "ping":
                    await connection_manager.send_personal_message({
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    }, connection_id)
                
                elif message_type == "get_event_status":
                    # Send current event status
                    countdown_status = countdown_manager.get_countdown_status(event_id)
                    await connection_manager.send_personal_message({
                        "type": "event_status",
                        "event_id": str(event_id),
                        "event_status": event.status.value,
                        "current_round": getattr(event, 'current_round_number', None),
                        "countdown_status": countdown_status
                    }, connection_id)
                    
                elif message_type == "get_countdown_status":
                    # Send current countdown status
                    countdown_status = countdown_manager.get_countdown_status(event_id)
                    await connection_manager.send_personal_message({
                        "type": "countdown_status",
                        "countdown_status": countdown_status
                    }, connection_id)
                
                elif message_type == "request_timer_sync" and user.is_organizer:
                    # Send current timer status for all rounds
                    active_timers = timer_manager.get_all_active_timers()
                    await connection_manager.send_personal_message({
                        "type": "timer_sync",
                        "active_timers": active_timers
                    }, connection_id)
                
        except WebSocketDisconnect:
            pass
        
    except Exception as e:
        print(f"WebSocket error in event room {event_id}: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
    
    finally:
        connection_manager.disconnect(connection_id)


@router.websocket("/ws/round/{round_id}/timer")
async def websocket_round_timer(
    websocket: WebSocket,
    round_id: uuid.UUID,
    token: str,
    session: AsyncSession = Depends(get_async_session)
):
    """WebSocket endpoint for real-time round timer updates."""
    
    try:
        # Authenticate user
        user = await get_current_user_websocket(token, session)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Verify access to round
        from sqlalchemy import select, and_
        from sqlalchemy.orm import selectinload
        
        round_result = await session.execute(
            select(Round)
            .options(selectinload(Round.event))
            .where(Round.id == round_id)
        )
        round_obj = round_result.scalar_one_or_none()
        
        if not round_obj:
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return
        
        # Check if user has access to this round
        if user.is_organizer:
            # Organizers can access rounds for events they own
            if round_obj.event.organizer_id != user.id:
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA) 
                return
        else:
            # Regular users can access rounds for events they're attending
            from app.models import Attendee
            attendee_result = await session.execute(
                select(Attendee).where(
                    and_(
                        Attendee.user_id == user.id,
                        Attendee.event_id == round_obj.event_id
                    )
                )
            )
            if not attendee_result.scalar_one_or_none():
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return
        
        # Generate connection ID and connect
        connection_id = str(uuid.uuid4())
        await connection_manager.connect(
            websocket,
            connection_id,
            user,
            room_type="round_timer",
            room_id=round_id
        )
        
        # Send welcome message with current timer status
        timer_status = timer_manager.get_timer_status(round_id)
        await connection_manager.send_personal_message({
            "type": "timer_connected",
            "round_id": str(round_id),
            "round_number": round_obj.round_number,
            "round_name": round_obj.name,
            "timer_status": timer_status
        }, connection_id)
        
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                message = json.loads(data)
                message_type = message.get("type")
                
                # Handle different message types
                if message_type == "ping":
                    await connection_manager.send_personal_message({
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    }, connection_id)
                
                elif message_type == "get_timer_status":
                    # Send current timer status
                    timer_status = timer_manager.get_timer_status(round_id)
                    await connection_manager.send_personal_message({
                        "type": "timer_status",
                        "timer_status": timer_status
                    }, connection_id)
                
                elif message_type == "get_round_info":
                    # Send round information
                    await connection_manager.send_personal_message({
                        "type": "round_info",
                        "round": {
                            "id": str(round_obj.id),
                            "number": round_obj.round_number,
                            "name": round_obj.name,
                            "status": round_obj.status.value,
                            "duration_minutes": round_obj.duration_minutes,
                            "break_minutes": round_obj.break_after_minutes,
                            "total_matches": round_obj.total_matches,
                            "completed_matches": round_obj.completed_matches,
                            "completion_percentage": round_obj.completion_percentage
                        }
                    }, connection_id)
                
        except WebSocketDisconnect:
            pass
    
    except Exception as e:
        print(f"WebSocket error in round timer {round_id}: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
    
    finally:
        connection_manager.disconnect(connection_id)


@router.websocket("/ws/admin/dashboard")
async def websocket_admin_dashboard(
    websocket: WebSocket,
    token: str,
    session: AsyncSession = Depends(get_async_session)
):
    """WebSocket endpoint for admin dashboard real-time updates."""
    
    try:
        # Authenticate user
        user = await get_current_user_websocket(token, session)
        if not user or not user.is_organizer:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Generate connection ID and connect
        connection_id = str(uuid.uuid4())
        await connection_manager.connect(
            websocket,
            connection_id,
            user,
            room_type="admin_dashboard"
        )
        
        # Send welcome message with connection stats
        stats = connection_manager.get_connection_stats()
        await connection_manager.send_personal_message({
            "type": "admin_connected",
            "message": "Connected to admin dashboard",
            "connection_stats": stats
        }, connection_id)
        
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                message = json.loads(data)
                message_type = message.get("type")
                
                # Handle different message types
                if message_type == "ping":
                    await connection_manager.send_personal_message({
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    }, connection_id)
                
                elif message_type == "get_connection_stats":
                    # Send current connection statistics
                    stats = connection_manager.get_connection_stats()
                    await connection_manager.send_personal_message({
                        "type": "connection_stats",
                        "stats": stats
                    }, connection_id)
                
                elif message_type == "get_active_timers":
                    # Send all active timer statuses
                    from app.services.websocket_manager import countdown_manager
                    active_timers = timer_manager.get_all_active_timers()
                    active_countdowns = countdown_manager.get_all_active_countdowns()
                    await connection_manager.send_personal_message({
                        "type": "active_timers",
                        "timers": active_timers,
                        "countdowns": active_countdowns
                    }, connection_id)
                
                elif message_type == "broadcast_announcement":
                    # Broadcast announcement to all connections
                    if message.get("event_id"):
                        event_id = uuid.UUID(message["event_id"])
                        await connection_manager.broadcast_to_event({
                            "type": "announcement",
                            "message": message.get("announcement", ""),
                            "from_admin": True
                        }, event_id)
                    else:
                        # Broadcast to all organizer connections
                        await connection_manager.broadcast_to_organizers({
                            "type": "announcement", 
                            "message": message.get("announcement", ""),
                            "from_admin": True
                        })
                
        except WebSocketDisconnect:
            pass
    
    except Exception as e:
        print(f"WebSocket error in admin dashboard: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
    
    finally:
        connection_manager.disconnect(connection_id)


# Health check endpoint for WebSocket
@router.get("/ws/health")
async def websocket_health():
    """Health check for WebSocket services."""
    from app.services.websocket_manager import countdown_manager
    
    stats = connection_manager.get_connection_stats()
    active_timers = timer_manager.get_all_active_timers()
    active_countdowns = countdown_manager.get_all_active_countdowns()
    
    return {
        "status": "healthy",
        "websocket_connections": stats,
        "active_timers": len(active_timers),
        "active_countdowns": len(active_countdowns),
        "services": {
            "connection_manager": "running",
            "timer_manager": "running",
            "countdown_manager": "running"
        }
    }