"""
WebSocket Connection Manager

Handles WebSocket connections, room management, and message broadcasting.
"""
import json
import uuid
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and handles broadcasting."""
    
    def __init__(self):
        # Active connections: {connection_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        
        # User to connection mapping: {user_id: connection_id}
        self.user_connections: Dict[uuid.UUID, str] = {}
        
        # Event rooms: {event_id: set of connection_ids}
        self.event_rooms: Dict[uuid.UUID, Set[str]] = {}
        
        # Connection metadata: {connection_id: metadata}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Heartbeat tracking
        self.last_heartbeat: Dict[str, datetime] = {}
    
    async def connect(
        self, 
        websocket: WebSocket, 
        user_id: uuid.UUID, 
        event_id: Optional[uuid.UUID] = None,
        connection_type: str = "general"
    ) -> str:
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        
        # Generate unique connection ID
        connection_id = f"{user_id}_{datetime.now().timestamp()}"
        
        # Store connection
        self.active_connections[connection_id] = websocket
        self.user_connections[user_id] = connection_id
        
        # Store metadata
        self.connection_metadata[connection_id] = {
            "user_id": user_id,
            "event_id": event_id,
            "connection_type": connection_type,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow()
        }
        
        # Add to event room if specified
        if event_id:
            await self.join_event_room(connection_id, event_id)
        
        # Track heartbeat
        self.last_heartbeat[connection_id] = datetime.utcnow()
        
        logger.info(f"WebSocket connected: {connection_id} (user: {user_id}, event: {event_id})")
        
        # Send welcome message
        await self.send_personal_message({
            "type": "connection_established",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat()
        }, connection_id)
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """Disconnect and clean up a WebSocket connection."""
        if connection_id not in self.active_connections:
            return
        
        # Get metadata before cleanup
        metadata = self.connection_metadata.get(connection_id, {})
        user_id = metadata.get("user_id")
        event_id = metadata.get("event_id")
        
        # Remove from active connections
        del self.active_connections[connection_id]
        
        # Remove user mapping
        if user_id and user_id in self.user_connections:
            del self.user_connections[user_id]
        
        # Remove from event rooms
        if event_id and event_id in self.event_rooms:
            self.event_rooms[event_id].discard(connection_id)
            if not self.event_rooms[event_id]:
                del self.event_rooms[event_id]
        
        # Clean up metadata and heartbeat
        self.connection_metadata.pop(connection_id, None)
        self.last_heartbeat.pop(connection_id, None)
        
        logger.info(f"WebSocket disconnected: {connection_id} (user: {user_id})")
    
    async def join_event_room(self, connection_id: str, event_id: uuid.UUID):
        """Add a connection to an event room."""
        if event_id not in self.event_rooms:
            self.event_rooms[event_id] = set()
        
        self.event_rooms[event_id].add(connection_id)
        
        # Update metadata
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["event_id"] = event_id
        
        logger.info(f"Connection {connection_id} joined event room {event_id}")
    
    async def leave_event_room(self, connection_id: str, event_id: uuid.UUID):
        """Remove a connection from an event room."""
        if event_id in self.event_rooms:
            self.event_rooms[event_id].discard(connection_id)
            if not self.event_rooms[event_id]:
                del self.event_rooms[event_id]
        
        logger.info(f"Connection {connection_id} left event room {event_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], connection_id: str):
        """Send a message to a specific connection."""
        if connection_id not in self.active_connections:
            return False
        
        try:
            websocket = self.active_connections[connection_id]
            await websocket.send_text(json.dumps(message))
            
            # Update last activity
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]["last_activity"] = datetime.utcnow()
            
            return True
        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False
    
    async def send_to_user(self, message: Dict[str, Any], user_id: uuid.UUID):
        """Send a message to a specific user."""
        connection_id = self.user_connections.get(user_id)
        if connection_id:
            return await self.send_personal_message(message, connection_id)
        return False
    
    async def broadcast_to_event(self, message: Dict[str, Any], event_id: uuid.UUID):
        """Broadcast a message to all connections in an event room."""
        if event_id not in self.event_rooms:
            return 0
        
        connection_ids = list(self.event_rooms[event_id])
        successful_sends = 0
        
        for connection_id in connection_ids:
            success = await self.send_personal_message(message, connection_id)
            if success:
                successful_sends += 1
        
        logger.info(f"Broadcast to event {event_id}: {successful_sends}/{len(connection_ids)} successful")
        return successful_sends
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast a message to all active connections."""
        connection_ids = list(self.active_connections.keys())
        successful_sends = 0
        
        for connection_id in connection_ids:
            success = await self.send_personal_message(message, connection_id)
            if success:
                successful_sends += 1
        
        logger.info(f"Broadcast to all: {successful_sends}/{len(connection_ids)} successful")
        return successful_sends
    
    async def handle_heartbeat(self, connection_id: str):
        """Handle heartbeat from a connection."""
        if connection_id in self.active_connections:
            self.last_heartbeat[connection_id] = datetime.utcnow()
            await self.send_personal_message({
                "type": "heartbeat_ack",
                "timestamp": datetime.utcnow().isoformat()
            }, connection_id)
    
    async def cleanup_stale_connections(self, timeout_minutes: int = 30):
        """Clean up connections that haven't sent heartbeat recently."""
        cutoff = datetime.utcnow().timestamp() - (timeout_minutes * 60)
        stale_connections = []
        
        for connection_id, last_beat in self.last_heartbeat.items():
            if last_beat.timestamp() < cutoff:
                stale_connections.append(connection_id)
        
        for connection_id in stale_connections:
            logger.info(f"Cleaning up stale connection: {connection_id}")
            await self.disconnect(connection_id)
        
        return len(stale_connections)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about active connections."""
        return {
            "total_connections": len(self.active_connections),
            "unique_users": len(self.user_connections),
            "active_event_rooms": len(self.event_rooms),
            "connections_per_room": {
                str(event_id): len(connections) 
                for event_id, connections in self.event_rooms.items()
            },
            "connection_types": {}
        }
    
    def get_event_connections(self, event_id: uuid.UUID) -> List[str]:
        """Get all connection IDs for an event."""
        return list(self.event_rooms.get(event_id, set()))
    
    def is_user_connected(self, user_id: uuid.UUID) -> bool:
        """Check if a user has an active connection."""
        return user_id in self.user_connections


# Global connection manager instance
connection_manager = ConnectionManager()


async def periodic_cleanup():
    """Background task to periodically clean up stale connections."""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            cleaned = await connection_manager.cleanup_stale_connections()
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} stale connections")
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying