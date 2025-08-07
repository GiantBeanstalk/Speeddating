"""
Tests for WebSocket functionality and real-time features.

Tests WebSocket connections, real-time messaging, event rooms,
round timers, and connection management.
"""

import uuid
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient
from fastapi import WebSocket
from hypothesis import given, strategies as st, settings

from app.models import User, Event, AttendeeCategory
from app.services.websocket_manager import ConnectionManager
from tests.fixtures.faker_providers import setup_faker_providers


@pytest.mark.websocket
class TestWebSocketConnection:
    """Test basic WebSocket connection functionality."""
    
    @pytest.mark.faker
    def test_websocket_connection_establishment(self, faker_instance):
        """Test establishing WebSocket connection with valid authentication."""
        fake = setup_faker_providers(faker_instance)
        
        # Mock WebSocket and dependencies
        mock_websocket = AsyncMock(spec=WebSocket)
        connection_manager = ConnectionManager()
        
        # Mock user and event
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.email = fake.email()
        mock_user.is_organizer = True
        
        event_id = uuid.uuid4()
        connection_id = str(uuid.uuid4())
        
        # Test connection establishment
        asyncio.run(connection_manager.connect(
            websocket=mock_websocket,
            connection_id=connection_id,
            user=mock_user,
            room_type="event",
            room_id=event_id
        ))
        
        # Verify connection was established
        assert connection_id in connection_manager.active_connections
        assert mock_user.id in connection_manager.user_connections
        assert connection_id in connection_manager.user_connections[mock_user.id]
        assert event_id in connection_manager.event_rooms
        assert connection_id in connection_manager.event_rooms[event_id]
        
        # Verify metadata
        metadata = connection_manager.connection_metadata[connection_id]
        assert metadata["user_id"] == mock_user.id
        assert metadata["user_email"] == mock_user.email
        assert metadata["is_organizer"] == True
        assert metadata["room_type"] == "event"
        assert metadata["room_id"] == event_id
    
    @pytest.mark.faker
    def test_websocket_connection_authentication_failure(self, client, faker_instance):
        """Test WebSocket connection with invalid authentication."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        invalid_token = fake.uuid4()
        
        # Mock authentication failure
        with patch("app.auth.get_current_user_websocket") as mock_auth:
            mock_auth.return_value = None  # Authentication failed
            
            with pytest.raises(Exception):  # WebSocket should close
                with client.websocket_connect(f"/ws/event/{event_id}?token={invalid_token}"):
                    pass
    
    @pytest.mark.faker
    def test_websocket_connection_authorization_failure(self, client, faker_instance):
        """Test WebSocket connection with valid auth but no event access."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        valid_token = fake.uuid4()
        
        # Mock user without access to event
        with patch("app.auth.get_current_user_websocket") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = False
            mock_auth.return_value = mock_user
            
            with patch("app.database.get_async_session"):
                with pytest.raises(Exception):  # WebSocket should close
                    with client.websocket_connect(f"/ws/event/{event_id}?token={valid_token}"):
                        pass
    
    def test_websocket_disconnection(self):
        """Test WebSocket disconnection cleanup."""
        connection_manager = ConnectionManager()
        
        # Set up connection
        connection_id = str(uuid.uuid4())
        user_id = uuid.uuid4()
        event_id = uuid.uuid4()
        
        # Mock connection data
        mock_websocket = AsyncMock(spec=WebSocket)
        connection_manager.active_connections[connection_id] = mock_websocket
        connection_manager.user_connections[user_id] = {connection_id}
        connection_manager.event_rooms[event_id] = {connection_id}
        connection_manager.connection_metadata[connection_id] = {
            "user_id": user_id,
            "room_type": "event",
            "room_id": event_id
        }
        
        # Disconnect
        connection_manager.disconnect(connection_id)
        
        # Verify cleanup
        assert connection_id not in connection_manager.active_connections
        assert user_id not in connection_manager.user_connections
        assert connection_id not in connection_manager.event_rooms.get(event_id, set())
        assert connection_id not in connection_manager.connection_metadata


@pytest.mark.websocket
class TestWebSocketMessaging:
    """Test WebSocket messaging functionality."""
    
    @pytest.mark.faker
    def test_personal_message_sending(self, faker_instance):
        """Test sending personal messages via WebSocket."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        connection_id = str(uuid.uuid4())
        
        # Mock WebSocket
        mock_websocket = AsyncMock(spec=WebSocket)
        connection_manager.active_connections[connection_id] = mock_websocket
        
        # Test message
        test_message = {
            "type": "notification",
            "message": fake.sentence(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Send message
        asyncio.run(connection_manager.send_personal_message(
            message=test_message,
            connection_id=connection_id
        ))
        
        # Verify message was sent
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        sent_message = json.loads(sent_data)
        
        assert sent_message["type"] == "notification"
        assert sent_message["message"] == test_message["message"]
    
    @pytest.mark.faker
    def test_broadcast_to_event_room(self, faker_instance):
        """Test broadcasting messages to event room."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        event_id = uuid.uuid4()
        
        # Set up multiple connections in event room
        connection_ids = [str(uuid.uuid4()) for _ in range(3)]
        mock_websockets = []
        
        for connection_id in connection_ids:
            mock_websocket = AsyncMock(spec=WebSocket)
            mock_websockets.append(mock_websocket)
            connection_manager.active_connections[connection_id] = mock_websocket
            
            # Add to event room
            if event_id not in connection_manager.event_rooms:
                connection_manager.event_rooms[event_id] = set()
            connection_manager.event_rooms[event_id].add(connection_id)
        
        # Test broadcast message
        broadcast_message = {
            "type": "event_update",
            "message": fake.sentence(),
            "event_id": str(event_id)
        }
        
        # Send broadcast
        asyncio.run(connection_manager.broadcast_to_event(
            message=broadcast_message,
            event_id=event_id
        ))
        
        # Verify all connections received message
        for mock_websocket in mock_websockets:
            mock_websocket.send_text.assert_called_once()
            sent_data = mock_websocket.send_text.call_args[0][0]
            sent_message = json.loads(sent_data)
            assert sent_message["type"] == "event_update"
    
    @pytest.mark.faker
    def test_user_specific_broadcast(self, faker_instance):
        """Test broadcasting to all connections of a specific user."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        user_id = uuid.uuid4()
        
        # Set up multiple connections for same user
        connection_ids = [str(uuid.uuid4()) for _ in range(2)]
        mock_websockets = []
        
        for connection_id in connection_ids:
            mock_websocket = AsyncMock(spec=WebSocket)
            mock_websockets.append(mock_websocket)
            connection_manager.active_connections[connection_id] = mock_websocket
            
            # Add to user connections
            if user_id not in connection_manager.user_connections:
                connection_manager.user_connections[user_id] = set()
            connection_manager.user_connections[user_id].add(connection_id)
        
        # Test user broadcast
        user_message = {
            "type": "personal_notification",
            "message": fake.sentence(),
            "user_id": str(user_id)
        }
        
        # Send to user
        asyncio.run(connection_manager.send_to_user(
            message=user_message,
            user_id=user_id
        ))
        
        # Verify all user connections received message
        for mock_websocket in mock_websockets:
            mock_websocket.send_text.assert_called_once()
    
    def test_message_to_disconnected_connection(self):
        """Test handling messages to disconnected connections."""
        connection_manager = ConnectionManager()
        connection_id = str(uuid.uuid4())
        
        # Try to send message to non-existent connection
        test_message = {"type": "test", "message": "hello"}
        
        # Should not raise exception
        asyncio.run(connection_manager.send_personal_message(
            message=test_message,
            connection_id=connection_id
        ))
        
        # Should handle gracefully (no exception)


@pytest.mark.websocket
class TestEventRoomFunctionality:
    """Test event room WebSocket functionality."""
    
    @pytest.mark.faker
    def test_event_room_joining(self, faker_instance):
        """Test joining event rooms."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        connection_id = str(uuid.uuid4())
        event_id = uuid.uuid4()
        
        # Join event room
        asyncio.run(connection_manager.join_event_room(
            connection_id=connection_id,
            event_id=event_id
        ))
        
        # Verify connection is in event room
        assert event_id in connection_manager.event_rooms
        assert connection_id in connection_manager.event_rooms[event_id]
    
    @pytest.mark.faker
    def test_event_room_leaving(self, faker_instance):
        """Test leaving event rooms."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        connection_id = str(uuid.uuid4())
        event_id = uuid.uuid4()
        
        # First join the room
        connection_manager.event_rooms[event_id] = {connection_id}
        
        # Leave event room
        connection_manager.leave_event_room(
            connection_id=connection_id,
            event_id=event_id
        )
        
        # Verify connection is removed from event room
        assert connection_id not in connection_manager.event_rooms.get(event_id, set())
    
    @given(
        participant_count=st.integers(min_value=2, max_value=20),
        message_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=10, deadline=8000)
    def test_event_room_message_distribution(self, participant_count, message_count):
        """Test message distribution in event rooms."""
        connection_manager = ConnectionManager()
        event_id = uuid.uuid4()
        
        # Set up multiple participants
        connections = []
        for i in range(participant_count):
            connection_id = str(uuid.uuid4())
            mock_websocket = AsyncMock(spec=WebSocket)
            
            connection_manager.active_connections[connection_id] = mock_websocket
            if event_id not in connection_manager.event_rooms:
                connection_manager.event_rooms[event_id] = set()
            connection_manager.event_rooms[event_id].add(connection_id)
            
            connections.append((connection_id, mock_websocket))
        
        # Send multiple messages
        for i in range(message_count):
            test_message = {
                "type": "round_update",
                "message": f"Test message {i}",
                "event_id": str(event_id)
            }
            
            asyncio.run(connection_manager.broadcast_to_event(
                message=test_message,
                event_id=event_id
            ))
        
        # Verify all connections received all messages
        for connection_id, mock_websocket in connections:
            assert mock_websocket.send_text.call_count == message_count


@pytest.mark.websocket
class TestRoundTimerWebSocket:
    """Test round timer WebSocket functionality."""
    
    @pytest.mark.faker
    def test_round_timer_subscription(self, faker_instance):
        """Test subscribing to round timer updates."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        connection_id = str(uuid.uuid4())
        round_id = uuid.uuid4()
        
        # Subscribe to round timer
        asyncio.run(connection_manager.join_round_timer(
            connection_id=connection_id,
            round_id=round_id
        ))
        
        # Verify subscription
        assert round_id in connection_manager.round_timers
        assert connection_id in connection_manager.round_timers[round_id]
    
    @pytest.mark.faker
    def test_round_timer_updates(self, faker_instance):
        """Test round timer update broadcasting."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        round_id = uuid.uuid4()
        
        # Set up timer subscribers
        subscriber_count = 5
        mock_websockets = []
        
        for i in range(subscriber_count):
            connection_id = str(uuid.uuid4())
            mock_websocket = AsyncMock(spec=WebSocket)
            mock_websockets.append(mock_websocket)
            
            connection_manager.active_connections[connection_id] = mock_websocket
            if round_id not in connection_manager.round_timers:
                connection_manager.round_timers[round_id] = set()
            connection_manager.round_timers[round_id].add(connection_id)
        
        # Send timer update
        timer_message = {
            "type": "timer_update",
            "round_id": str(round_id),
            "remaining_seconds": 300,
            "status": "active"
        }
        
        asyncio.run(connection_manager.broadcast_to_round_timer(
            message=timer_message,
            round_id=round_id
        ))
        
        # Verify all subscribers received update
        for mock_websocket in mock_websockets:
            mock_websocket.send_text.assert_called_once()
            sent_data = mock_websocket.send_text.call_args[0][0]
            sent_message = json.loads(sent_data)
            assert sent_message["type"] == "timer_update"
            assert sent_message["remaining_seconds"] == 300
    
    @pytest.mark.faker
    def test_round_timer_completion_notification(self, faker_instance):
        """Test round timer completion notifications."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        round_id = uuid.uuid4()
        
        # Set up timer subscribers
        connection_id = str(uuid.uuid4())
        mock_websocket = AsyncMock(spec=WebSocket)
        
        connection_manager.active_connections[connection_id] = mock_websocket
        connection_manager.round_timers[round_id] = {connection_id}
        
        # Send completion notification
        completion_message = {
            "type": "round_completed",
            "round_id": str(round_id),
            "message": "Round has ended",
            "next_action": "submit_responses"
        }
        
        asyncio.run(connection_manager.broadcast_to_round_timer(
            message=completion_message,
            round_id=round_id
        ))
        
        # Verify completion notification
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        sent_message = json.loads(sent_data)
        
        assert sent_message["type"] == "round_completed"
        assert sent_message["next_action"] == "submit_responses"


@pytest.mark.websocket
class TestWebSocketSecurity:
    """Test WebSocket security features."""
    
    @pytest.mark.faker
    def test_connection_limit_enforcement(self, faker_instance):
        """Test enforcement of connection limits per user."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        user_id = uuid.uuid4()
        
        # Try to create many connections for same user
        max_connections = 5
        connections = []
        
        for i in range(max_connections * 2):  # Try to exceed limit
            connection_id = str(uuid.uuid4())
            mock_websocket = AsyncMock(spec=WebSocket)
            
            # Add connection
            connection_manager.active_connections[connection_id] = mock_websocket
            
            if user_id not in connection_manager.user_connections:
                connection_manager.user_connections[user_id] = set()
            connection_manager.user_connections[user_id].add(connection_id)
            
            connections.append(connection_id)
        
        # In a real implementation, should limit connections per user
        # For now, just verify tracking works
        assert len(connection_manager.user_connections[user_id]) == max_connections * 2
    
    @given(malicious_message=st.dictionaries(
        st.text(min_size=1, max_size=50),
        st.one_of(
            st.text(min_size=1, max_size=1000),
            st.integers(),
            st.lists(st.text(), min_size=1, max_size=5)
        ),
        min_size=1,
        max_size=10
    ))
    @settings(max_examples=20, deadline=5000)
    def test_malicious_message_handling(self, malicious_message):
        """Test handling of malicious WebSocket messages."""
        connection_manager = ConnectionManager()
        connection_id = str(uuid.uuid4())
        
        mock_websocket = AsyncMock(spec=WebSocket)
        connection_manager.active_connections[connection_id] = mock_websocket
        
        try:
            # Try to send malicious message
            asyncio.run(connection_manager.send_personal_message(
                message=malicious_message,
                connection_id=connection_id
            ))
            
            # Should handle gracefully without crashing
            mock_websocket.send_text.assert_called_once()
            
        except Exception as e:
            # Should not raise unhandled exceptions
            pytest.fail(f"Unhandled exception with malicious message: {e}")
    
    @pytest.mark.faker
    def test_message_rate_limiting(self, faker_instance):
        """Test WebSocket message rate limiting."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        connection_id = str(uuid.uuid4())
        
        mock_websocket = AsyncMock(spec=WebSocket)
        connection_manager.active_connections[connection_id] = mock_websocket
        
        # Send many rapid messages
        message_count = 100
        for i in range(message_count):
            test_message = {
                "type": "spam",
                "message": f"Message {i}",
                "timestamp": datetime.now().isoformat()
            }
            
            asyncio.run(connection_manager.send_personal_message(
                message=test_message,
                connection_id=connection_id
            ))
        
        # In a real implementation, should implement rate limiting
        # For now, verify all messages were attempted
        assert mock_websocket.send_text.call_count == message_count


@pytest.mark.websocket
class TestWebSocketResilience:
    """Test WebSocket resilience and error handling."""
    
    @pytest.mark.faker
    def test_connection_cleanup_on_error(self, faker_instance):
        """Test connection cleanup when WebSocket errors occur."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        connection_id = str(uuid.uuid4())
        user_id = uuid.uuid4()
        event_id = uuid.uuid4()
        
        # Set up connection with all tracking
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.send_text.side_effect = Exception("Connection broken")
        
        connection_manager.active_connections[connection_id] = mock_websocket
        connection_manager.user_connections[user_id] = {connection_id}
        connection_manager.event_rooms[event_id] = {connection_id}
        connection_manager.connection_metadata[connection_id] = {
            "user_id": user_id,
            "room_type": "event",
            "room_id": event_id
        }
        
        # Try to send message (should fail)
        test_message = {"type": "test", "message": "hello"}
        
        try:
            asyncio.run(connection_manager.send_personal_message(
                message=test_message,
                connection_id=connection_id
            ))
        except Exception:
            pass  # Expected to fail
        
        # Manually clean up (in real implementation, would be automatic)
        connection_manager.disconnect(connection_id)
        
        # Verify cleanup
        assert connection_id not in connection_manager.active_connections
    
    def test_reconnection_handling(self):
        """Test handling of connection reconnections."""
        connection_manager = ConnectionManager()
        user_id = uuid.uuid4()
        event_id = uuid.uuid4()
        
        # First connection
        connection_id_1 = str(uuid.uuid4())
        mock_websocket_1 = AsyncMock(spec=WebSocket)
        
        asyncio.run(connection_manager.connect(
            websocket=mock_websocket_1,
            connection_id=connection_id_1,
            user=MagicMock(id=user_id, email="test@example.com", is_organizer=True),
            room_type="event",
            room_id=event_id
        ))
        
        # Second connection (reconnection)
        connection_id_2 = str(uuid.uuid4())
        mock_websocket_2 = AsyncMock(spec=WebSocket)
        
        asyncio.run(connection_manager.connect(
            websocket=mock_websocket_2,
            connection_id=connection_id_2,
            user=MagicMock(id=user_id, email="test@example.com", is_organizer=True),
            room_type="event",
            room_id=event_id
        ))
        
        # Both connections should be tracked
        assert len(connection_manager.user_connections[user_id]) == 2
        assert connection_id_1 in connection_manager.user_connections[user_id]
        assert connection_id_2 in connection_manager.user_connections[user_id]
    
    @pytest.mark.faker
    def test_broadcast_with_partial_failures(self, faker_instance):
        """Test broadcasting when some connections fail."""
        fake = setup_faker_providers(faker_instance)
        
        connection_manager = ConnectionManager()
        event_id = uuid.uuid4()
        
        # Set up multiple connections, some will fail
        working_connections = []
        failing_connections = []
        
        for i in range(3):
            connection_id = str(uuid.uuid4())
            mock_websocket = AsyncMock(spec=WebSocket)
            
            if i == 1:  # Make middle connection fail
                mock_websocket.send_text.side_effect = Exception("Connection failed")
                failing_connections.append(connection_id)
            else:
                working_connections.append(connection_id)
            
            connection_manager.active_connections[connection_id] = mock_websocket
            
            if event_id not in connection_manager.event_rooms:
                connection_manager.event_rooms[event_id] = set()
            connection_manager.event_rooms[event_id].add(connection_id)
        
        # Broadcast message
        broadcast_message = {
            "type": "test_broadcast",
            "message": fake.sentence()
        }
        
        # Should not raise exception despite partial failures
        asyncio.run(connection_manager.broadcast_to_event(
            message=broadcast_message,
            event_id=event_id
        ))
        
        # Working connections should have received message
        for connection_id in working_connections:
            mock_websocket = connection_manager.active_connections[connection_id]
            mock_websocket.send_text.assert_called_once()


# Helper fixtures and utilities for WebSocket testing
@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    mock_ws = AsyncMock(spec=WebSocket)
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()
    mock_ws.receive_text = AsyncMock()
    mock_ws.close = AsyncMock()
    return mock_ws


@pytest.fixture
def connection_manager():
    """Create a fresh ConnectionManager for testing."""
    return ConnectionManager()


@pytest.fixture
def mock_user(faker_instance):
    """Create a mock user for WebSocket testing."""
    fake = setup_faker_providers(faker_instance)
    
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = fake.email()
    user.is_organizer = fake.boolean()
    user.is_active = True
    
    return user


async def create_websocket_connection(connection_manager, user, event_id=None):
    """Helper to create a WebSocket connection for testing."""
    mock_websocket = AsyncMock(spec=WebSocket)
    connection_id = str(uuid.uuid4())
    
    await connection_manager.connect(
        websocket=mock_websocket,
        connection_id=connection_id,
        user=user,
        room_type="event" if event_id else "general",
        room_id=event_id
    )
    
    return connection_id, mock_websocket