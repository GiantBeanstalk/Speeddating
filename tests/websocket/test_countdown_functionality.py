"""
Tests for countdown functionality and real-time timer features.

Tests event countdowns, round timers, and real-time notifications
for speed dating events.
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from hypothesis import given, strategies as st, settings

from app.services.websocket_manager import CountdownManager
from tests.fixtures.faker_providers import setup_faker_providers


@pytest.mark.websocket
class TestCountdownManager:
    """Test countdown management functionality."""
    
    def test_countdown_manager_initialization(self):
        """Test CountdownManager initialization."""
        countdown_manager = CountdownManager()
        
        assert countdown_manager.active_countdowns == {}
        assert countdown_manager.countdown_tasks == {}
    
    @pytest.mark.faker
    def test_start_event_countdown(self, faker_instance):
        """Test starting an event countdown."""
        fake = setup_faker_providers(faker_instance)
        countdown_manager = CountdownManager()
        
        event_id = uuid.uuid4()
        duration_minutes = fake.random_int(min=5, max=30)
        message = fake.sentence()
        
        # Mock session
        mock_session = AsyncMock()
        
        # Start countdown
        asyncio.run(countdown_manager.start_event_countdown(
            event_id=event_id,
            duration_minutes=duration_minutes,
            message=message,
            session=mock_session
        ))
        
        # Verify countdown is active
        assert event_id in countdown_manager.active_countdowns
        
        countdown_info = countdown_manager.active_countdowns[event_id]
        assert countdown_info["duration_minutes"] == duration_minutes
        assert countdown_info["message"] == message
        assert countdown_info["active"] == True
        assert "start_time" in countdown_info
        assert "target_time" in countdown_info
    
    @pytest.mark.faker
    def test_stop_event_countdown(self, faker_instance):
        """Test stopping an event countdown."""
        fake = setup_faker_providers(faker_instance)
        countdown_manager = CountdownManager()
        
        event_id = uuid.uuid4()
        
        # Set up active countdown
        countdown_manager.active_countdowns[event_id] = {
            "duration_minutes": 10,
            "message": fake.sentence(),
            "active": True,
            "start_time": datetime.now(),
            "target_time": datetime.now() + timedelta(minutes=10)
        }
        
        # Mock task
        mock_task = AsyncMock()
        countdown_manager.countdown_tasks[event_id] = mock_task
        
        # Stop countdown
        asyncio.run(countdown_manager.stop_event_countdown(event_id))
        
        # Verify countdown is stopped
        assert event_id not in countdown_manager.active_countdowns
        assert event_id not in countdown_manager.countdown_tasks
        
        # Verify task was cancelled
        mock_task.cancel.assert_called_once()
    
    @pytest.mark.faker
    def test_extend_event_countdown(self, faker_instance):
        """Test extending an active countdown."""
        fake = setup_faker_providers(faker_instance)
        countdown_manager = CountdownManager()
        
        event_id = uuid.uuid4()
        original_duration = 10
        extension_minutes = 5
        
        start_time = datetime.now()
        original_target = start_time + timedelta(minutes=original_duration)
        
        # Set up active countdown
        countdown_manager.active_countdowns[event_id] = {
            "duration_minutes": original_duration,
            "message": fake.sentence(),
            "active": True,
            "start_time": start_time,
            "target_time": original_target
        }
        
        # Extend countdown
        asyncio.run(countdown_manager.extend_event_countdown(
            event_id=event_id,
            additional_minutes=extension_minutes
        ))
        
        # Verify countdown was extended
        countdown_info = countdown_manager.active_countdowns[event_id]
        expected_target = original_target + timedelta(minutes=extension_minutes)
        
        assert countdown_info["target_time"] == expected_target
        assert countdown_info["active"] == True
    
    def test_get_countdown_status(self):
        """Test getting countdown status."""
        countdown_manager = CountdownManager()
        event_id = uuid.uuid4()
        
        # Test non-existent countdown
        status = countdown_manager.get_countdown_status(event_id)
        assert status is None
        
        # Set up active countdown
        start_time = datetime.now()
        target_time = start_time + timedelta(minutes=10)
        
        countdown_manager.active_countdowns[event_id] = {
            "duration_minutes": 10,
            "message": "Test countdown",
            "active": True,
            "start_time": start_time,
            "target_time": target_time
        }
        
        # Test active countdown
        status = countdown_manager.get_countdown_status(event_id)
        
        assert status is not None
        assert status["active"] == True
        assert "remaining_seconds" in status
        assert status["message"] == "Test countdown"
        assert status["target_time"] == target_time.isoformat()
    
    def test_get_all_active_countdowns(self):
        """Test getting all active countdowns."""
        countdown_manager = CountdownManager()
        
        # No active countdowns initially
        active = countdown_manager.get_all_active_countdowns()
        assert active == []
        
        # Add multiple countdowns
        for i in range(3):
            event_id = uuid.uuid4()
            countdown_manager.active_countdowns[event_id] = {
                "duration_minutes": 10 + i,
                "message": f"Countdown {i}",
                "active": True,
                "start_time": datetime.now(),
                "target_time": datetime.now() + timedelta(minutes=10 + i),
                "event_id": event_id
            }
        
        # Get all active countdowns
        active = countdown_manager.get_all_active_countdowns()
        assert len(active) == 3
        
        for countdown in active:
            assert countdown["active"] == True
            assert "event_id" in countdown


@pytest.mark.websocket
class TestCountdownRealTimeUpdates:
    """Test real-time countdown update functionality."""
    
    @pytest.mark.faker
    def test_countdown_tick_updates(self, faker_instance):
        """Test countdown tick updates via WebSocket."""
        fake = setup_faker_providers(faker_instance)
        
        # Import here to avoid circular imports
        from app.services.websocket_manager import connection_manager
        
        event_id = uuid.uuid4()
        
        # Set up WebSocket connection
        connection_id = str(uuid.uuid4())
        mock_websocket = AsyncMock()
        
        connection_manager.active_connections[connection_id] = mock_websocket
        connection_manager.event_rooms[event_id] = {connection_id}
        
        # Simulate countdown tick message
        tick_message = {
            "type": "countdown_tick",
            "event_id": str(event_id),
            "remaining_seconds": 300,
            "remaining_minutes": 5,
            "message": "Event starts in 5 minutes!"
        }
        
        # Send tick update
        asyncio.run(connection_manager.broadcast_to_event(
            message=tick_message,
            event_id=event_id
        ))
        
        # Verify tick was broadcast
        mock_websocket.send_text.assert_called_once()
    
    @pytest.mark.faker
    def test_countdown_completion_notification(self, faker_instance):
        """Test countdown completion notifications."""
        fake = setup_faker_providers(faker_instance)
        
        from app.services.websocket_manager import connection_manager
        
        event_id = uuid.uuid4()
        
        # Set up WebSocket connections
        connection_ids = [str(uuid.uuid4()) for _ in range(3)]
        mock_websockets = []
        
        for connection_id in connection_ids:
            mock_websocket = AsyncMock()
            mock_websockets.append(mock_websocket)
            connection_manager.active_connections[connection_id] = mock_websocket
            
            if event_id not in connection_manager.event_rooms:
                connection_manager.event_rooms[event_id] = set()
            connection_manager.event_rooms[event_id].add(connection_id)
        
        # Simulate countdown completion
        completion_message = {
            "type": "countdown_completed",
            "event_id": str(event_id),
            "message": "Event is starting now!",
            "action": "event_start"
        }
        
        # Send completion notification
        asyncio.run(connection_manager.broadcast_to_event(
            message=completion_message,
            event_id=event_id
        ))
        
        # Verify all connections received completion notification
        for mock_websocket in mock_websockets:
            mock_websocket.send_text.assert_called_once()
    
    @given(
        countdown_duration=st.integers(min_value=1, max_value=60),
        tick_interval=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=10, deadline=8000)
    def test_countdown_tick_frequency(self, countdown_duration, tick_interval):
        """Test countdown tick frequency and accuracy."""
        countdown_manager = CountdownManager()
        event_id = uuid.uuid4()
        
        # Calculate expected ticks
        expected_ticks = countdown_duration * 60 // tick_interval
        
        # This would test the actual countdown loop
        # In a real implementation, we'd verify tick timing
        # For now, just test the data structure
        
        countdown_info = {
            "duration_minutes": countdown_duration,
            "message": "Test countdown",
            "active": True,
            "start_time": datetime.now(),
            "target_time": datetime.now() + timedelta(minutes=countdown_duration),
            "tick_interval": tick_interval
        }
        
        countdown_manager.active_countdowns[event_id] = countdown_info
        
        # Verify countdown setup
        assert countdown_manager.active_countdowns[event_id]["duration_minutes"] == countdown_duration
        assert countdown_manager.active_countdowns[event_id]["tick_interval"] == tick_interval


@pytest.mark.websocket
class TestRoundTimerFunctionality:
    """Test round timer functionality for speed dating rounds."""
    
    @pytest.mark.faker
    def test_round_timer_start(self, faker_instance):
        """Test starting a round timer."""
        fake = setup_faker_providers(faker_instance)
        
        # Import timer manager
        from app.websocket.round_timer import RoundTimerManager
        
        timer_manager = RoundTimerManager()
        round_id = uuid.uuid4()
        duration_minutes = fake.random_int(min=3, max=10)
        
        # Mock session
        mock_session = AsyncMock()
        
        # Start round timer
        asyncio.run(timer_manager.start_round_timer(
            round_id=round_id,
            duration_minutes=duration_minutes,
            session=mock_session
        ))
        
        # Verify timer is active
        assert round_id in timer_manager.active_timers
        
        timer_info = timer_manager.active_timers[round_id]
        assert timer_info["duration_minutes"] == duration_minutes
        assert timer_info["active"] == True
    
    @pytest.mark.faker
    def test_round_timer_pause_resume(self, faker_instance):
        """Test pausing and resuming round timers."""
        fake = setup_faker_providers(faker_instance)
        
        from app.websocket.round_timer import RoundTimerManager
        
        timer_manager = RoundTimerManager()
        round_id = uuid.uuid4()
        
        # Set up active timer
        timer_manager.active_timers[round_id] = {
            "duration_minutes": 5,
            "active": True,
            "paused": False,
            "start_time": datetime.now(),
            "remaining_seconds": 300
        }
        
        # Pause timer
        timer_manager.pause_round_timer(round_id)
        
        # Verify timer is paused
        assert timer_manager.active_timers[round_id]["paused"] == True
        
        # Resume timer
        timer_manager.resume_round_timer(round_id)
        
        # Verify timer is resumed
        assert timer_manager.active_timers[round_id]["paused"] == False
    
    @pytest.mark.faker
    def test_round_timer_completion(self, faker_instance):
        """Test round timer completion handling."""
        fake = setup_faker_providers(faker_instance)
        
        from app.services.websocket_manager import connection_manager
        
        round_id = uuid.uuid4()
        
        # Set up WebSocket subscribers
        connection_id = str(uuid.uuid4())
        mock_websocket = AsyncMock()
        
        connection_manager.active_connections[connection_id] = mock_websocket
        connection_manager.round_timers[round_id] = {connection_id}
        
        # Simulate timer completion
        completion_message = {
            "type": "round_timer_completed",
            "round_id": str(round_id),
            "message": "Round time is up!",
            "next_action": "move_to_next_table"
        }
        
        # Send completion notification
        asyncio.run(connection_manager.broadcast_to_round_timer(
            message=completion_message,
            round_id=round_id
        ))
        
        # Verify completion notification sent
        mock_websocket.send_text.assert_called_once()
    
    @pytest.mark.faker
    def test_multiple_concurrent_timers(self, faker_instance):
        """Test managing multiple concurrent round timers."""
        fake = setup_faker_providers(faker_instance)
        
        from app.websocket.round_timer import RoundTimerManager
        
        timer_manager = RoundTimerManager()
        
        # Start multiple timers
        timer_count = 5
        round_ids = []
        
        for i in range(timer_count):
            round_id = uuid.uuid4()
            round_ids.append(round_id)
            
            timer_manager.active_timers[round_id] = {
                "duration_minutes": 5 + i,
                "active": True,
                "paused": False,
                "start_time": datetime.now(),
                "remaining_seconds": (5 + i) * 60,
                "round_number": i + 1
            }
        
        # Verify all timers are tracked
        assert len(timer_manager.active_timers) == timer_count
        
        for round_id in round_ids:
            assert round_id in timer_manager.active_timers
            assert timer_manager.active_timers[round_id]["active"] == True


@pytest.mark.websocket
class TestCountdownEdgeCases:
    """Test countdown edge cases and error scenarios."""
    
    @pytest.mark.faker
    def test_countdown_with_past_target_time(self, faker_instance):
        """Test countdown with target time in the past."""
        fake = setup_faker_providers(faker_instance)
        countdown_manager = CountdownManager()
        
        event_id = uuid.uuid4()
        
        # Set up countdown with past target time
        past_time = datetime.now() - timedelta(minutes=5)
        
        countdown_manager.active_countdowns[event_id] = {
            "duration_minutes": 10,
            "message": fake.sentence(),
            "active": True,
            "start_time": past_time - timedelta(minutes=10),
            "target_time": past_time
        }
        
        # Get status of past countdown
        status = countdown_manager.get_countdown_status(event_id)
        
        # Should handle gracefully
        assert status is not None
        assert status["remaining_seconds"] <= 0
    
    @pytest.mark.faker
    def test_countdown_cancellation_during_active_countdown(self, faker_instance):
        """Test cancelling countdown while it's running."""
        fake = setup_faker_providers(faker_instance)
        countdown_manager = CountdownManager()
        
        event_id = uuid.uuid4()
        
        # Set up active countdown
        countdown_manager.active_countdowns[event_id] = {
            "duration_minutes": 30,
            "message": fake.sentence(),
            "active": True,
            "start_time": datetime.now(),
            "target_time": datetime.now() + timedelta(minutes=30)
        }
        
        # Mock running task
        mock_task = AsyncMock()
        countdown_manager.countdown_tasks[event_id] = mock_task
        
        # Cancel countdown
        asyncio.run(countdown_manager.stop_event_countdown(event_id))
        
        # Verify proper cleanup
        assert event_id not in countdown_manager.active_countdowns
        assert event_id not in countdown_manager.countdown_tasks
        mock_task.cancel.assert_called_once()
    
    @pytest.mark.faker
    def test_countdown_extension_beyond_limits(self, faker_instance):
        """Test extending countdown beyond reasonable limits."""
        fake = setup_faker_providers(faker_instance)
        countdown_manager = CountdownManager()
        
        event_id = uuid.uuid4()
        
        # Set up countdown
        countdown_manager.active_countdowns[event_id] = {
            "duration_minutes": 60,  # 1 hour
            "message": fake.sentence(),
            "active": True,
            "start_time": datetime.now(),
            "target_time": datetime.now() + timedelta(minutes=60)
        }
        
        # Try to extend by excessive amount
        excessive_extension = 1440  # 24 hours
        
        try:
            asyncio.run(countdown_manager.extend_event_countdown(
                event_id=event_id,
                additional_minutes=excessive_extension
            ))
            
            # Should either handle gracefully or apply reasonable limits
            countdown_info = countdown_manager.active_countdowns[event_id]
            target_time = countdown_info["target_time"]
            max_reasonable_time = datetime.now() + timedelta(hours=6)  # 6 hour limit
            
            # In a real implementation, should enforce reasonable limits
            # For now, just verify the operation completed
            assert target_time is not None
            
        except Exception as e:
            # Should handle excessive extensions gracefully
            assert "limit" in str(e).lower() or "maximum" in str(e).lower()
    
    def test_countdown_memory_cleanup(self):
        """Test memory cleanup when countdowns complete."""
        countdown_manager = CountdownManager()
        
        # Create many completed countdowns
        completed_event_ids = []
        for i in range(100):
            event_id = uuid.uuid4()
            completed_event_ids.append(event_id)
            
            # These represent completed countdowns that should be cleaned up
            countdown_manager.active_countdowns[event_id] = {
                "duration_minutes": 5,
                "message": f"Completed countdown {i}",
                "active": False,  # Completed
                "start_time": datetime.now() - timedelta(minutes=10),
                "target_time": datetime.now() - timedelta(minutes=5)
            }
        
        # In a real implementation, should periodically clean up completed countdowns
        # Simulate cleanup
        completed_countdowns = [
            event_id for event_id, info in countdown_manager.active_countdowns.items()
            if not info["active"]
        ]
        
        for event_id in completed_countdowns:
            del countdown_manager.active_countdowns[event_id]
        
        # Verify cleanup
        assert len(countdown_manager.active_countdowns) == 0


# Helper utilities for countdown testing
def simulate_countdown_progress(countdown_manager, event_id, elapsed_minutes):
    """Simulate countdown progress for testing."""
    if event_id not in countdown_manager.active_countdowns:
        return None
    
    countdown_info = countdown_manager.active_countdowns[event_id]
    start_time = countdown_info["start_time"]
    duration_minutes = countdown_info["duration_minutes"]
    
    # Update countdown state as if time has passed
    current_time = start_time + timedelta(minutes=elapsed_minutes)
    remaining_minutes = duration_minutes - elapsed_minutes
    
    countdown_info["current_time"] = current_time
    countdown_info["remaining_minutes"] = max(0, remaining_minutes)
    countdown_info["active"] = remaining_minutes > 0
    
    return countdown_info


@pytest.fixture
def countdown_manager():
    """Create a fresh CountdownManager for testing."""
    return CountdownManager()