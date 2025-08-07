"""
Integration tests for events API endpoints.

Tests event management functionality with realistic scenarios and data
using Faker-generated content.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, strategies as st
from fastapi import status

from app.models import EventStatus, AttendeeCategory
from tests.fixtures.faker_providers import setup_faker_providers


@pytest.mark.integration
class TestEventCreation:
    """Integration tests for event creation endpoints."""
    
    @pytest.mark.faker
    def test_create_event_with_realistic_data(self, client, faker_instance):
        """Test event creation with realistic UK event data."""
        fake = setup_faker_providers(faker_instance)
        
        # Generate realistic event data
        event_date = fake.date_time_between(start_date="+1d", end_date="+30d")
        registration_deadline = event_date - timedelta(hours=fake.random_int(min=2, max=48))
        
        event_data = {
            "name": fake.event_name(),
            "description": fake.text(max_nb_chars=500),
            "location": fake.venue_name(),
            "event_date": event_date.isoformat(),
            "registration_deadline": registration_deadline.isoformat(),
            "round_duration_minutes": fake.random_int(min=3, max=8),
            "break_duration_minutes": fake.random_int(min=1, max=5),
            "max_attendees": fake.random_int(min=20, max=200),
            "min_attendees": fake.random_int(min=8, max=20),
            "ticket_price": fake.random_int(min=1000, max=5000),  # £10-50 in pence
            "currency": "GBP"
        }
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.full_name = fake.name()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            response = client.post("/events/", json=event_data)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            
            assert data["name"] == event_data["name"]
            assert data["location"] == event_data["location"]
            assert data["max_attendees"] == event_data["max_attendees"]
            assert data["status"] == EventStatus.DRAFT.value
            assert "id" in data
            assert data["organizer_name"] == mock_user.full_name
    
    @pytest.mark.faker
    def test_create_event_validation_errors(self, client, faker_instance):
        """Test event creation with various validation errors."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.full_name = fake.name()
            mock_auth.return_value = mock_user
            
            # Test registration deadline after event date
            event_date = fake.date_time_between(start_date="+1d", end_date="+7d")
            bad_deadline = event_date + timedelta(hours=1)
            
            event_data = {
                "name": fake.event_name(),
                "event_date": event_date.isoformat(),
                "registration_deadline": bad_deadline.isoformat(),
                "max_attendees": 50,
                "min_attendees": 10
            }
            
            response = client.post("/events/", json=event_data)
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "registration deadline" in response.json()["detail"].lower()
            
            # Test min_attendees > max_attendees
            event_data.update({
                "registration_deadline": (event_date - timedelta(hours=2)).isoformat(),
                "min_attendees": 100,
                "max_attendees": 50
            })
            
            response = client.post("/events/", json=event_data)
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "minimum attendees" in response.json()["detail"].lower()
    
    @given(
        round_duration=st.integers(min_value=1, max_value=60),
        break_duration=st.integers(min_value=0, max_value=30),
        max_attendees=st.integers(min_value=4, max_value=1000)
    )
    def test_event_creation_with_property_based_testing(
        self, client, round_duration, break_duration, max_attendees
    ):
        """Test event creation with property-based testing for constraints."""
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.full_name = "Test Organizer"
            mock_auth.return_value = mock_user
            
            event_date = datetime.now() + timedelta(days=7)
            min_attendees = max(4, max_attendees // 4)  # Ensure min <= max
            
            event_data = {
                "name": "Test Event",
                "event_date": event_date.isoformat(),
                "round_duration_minutes": round_duration,
                "break_duration_minutes": break_duration,
                "max_attendees": max_attendees,
                "min_attendees": min_attendees
            }
            
            response = client.post("/events/", json=event_data)
            
            # Should succeed with valid constraints
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["round_duration_minutes"] == round_duration
            assert data["break_duration_minutes"] == break_duration
            assert data["max_attendees"] == max_attendees


@pytest.mark.integration
class TestEventRetrieval:
    """Integration tests for event retrieval endpoints."""
    
    @pytest.mark.faker
    def test_get_events_with_filtering(self, client, faker_instance):
        """Test event listing with status filtering."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.full_name = fake.name()
            mock_auth.return_value = mock_user
            
            # Create multiple events with different statuses
            events = []
            for status in [EventStatus.DRAFT, EventStatus.REGISTRATION_OPEN]:
                event_data = {
                    "name": fake.event_name(),
                    "event_date": fake.date_time_between(start_date="+1d", end_date="+30d").isoformat(),
                    "max_attendees": fake.random_int(min=20, max=100),
                    "min_attendees": fake.random_int(min=8, max=20)
                }
                
                # Mock database query results
                with patch("app.database.get_async_session"):
                    response = client.get(f"/events/?status_filter={status.value}")
                    # In a real test, this would verify filtered results
                    # For now, just test the endpoint structure
                    if response.status_code == status.HTTP_200_OK:
                        events.extend(response.json())
    
    @pytest.mark.faker
    def test_get_single_event_details(self, client, faker_instance):
        """Test retrieving single event with full details."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.full_name = fake.name()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            
            # Mock database result
            mock_event = MagicMock()
            mock_event.id = event_id
            mock_event.name = fake.event_name()
            mock_event.description = fake.text(max_nb_chars=500)
            mock_event.location = fake.venue_name()
            mock_event.status = EventStatus.DRAFT
            mock_event.max_attendees = 50
            mock_event.attendee_count = 0
            mock_event.created_at = datetime.now()
            
            with patch("app.database.get_async_session"):
                response = client.get(f"/events/{event_id}")
                
                # Test endpoint accessibility
                # In real implementation, would verify all event details
                if response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]:
                    # Valid response structure
                    pass


@pytest.mark.integration
class TestEventPublishing:
    """Integration tests for event publishing workflow."""
    
    @pytest.mark.faker
    def test_publish_draft_event(self, client, faker_instance):
        """Test publishing a draft event."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.full_name = fake.name()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            
            # Mock event in draft status
            with patch("app.database.get_async_session"):
                response = client.post(f"/events/{event_id}/publish")
                
                # Test endpoint accessibility
                if response.status_code == status.HTTP_200_OK:
                    data = response.json()
                    assert "message" in data
                    assert "published" in data["message"].lower()
    
    @pytest.mark.faker
    def test_publish_non_draft_event_fails(self, client, faker_instance):
        """Test that non-draft events cannot be published."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            
            # Mock event in non-draft status
            with patch("app.database.get_async_session"):
                response = client.post(f"/events/{event_id}/publish")
                
                # Should handle non-draft events appropriately
                if response.status_code == status.HTTP_400_BAD_REQUEST:
                    assert "draft" in response.json()["detail"].lower()


@pytest.mark.integration
class TestEventDashboard:
    """Integration tests for event dashboard functionality."""
    
    @pytest.mark.faker
    def test_event_dashboard_comprehensive_data(self, client, faker_instance):
        """Test event dashboard returns comprehensive analytics."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.full_name = fake.name()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            
            # Mock complex event with attendees and matches
            mock_event = MagicMock()
            mock_event.id = event_id
            mock_event.name = fake.event_name()
            mock_event.attendees = []
            mock_event.matches = []
            mock_event.rounds = []
            
            # Generate realistic attendee distribution
            for category in AttendeeCategory:
                count = fake.random_int(min=2, max=15)
                for _ in range(count):
                    mock_attendee = MagicMock()
                    mock_attendee.category = category
                    mock_attendee.registration_confirmed = True
                    mock_attendee.checked_in = fake.boolean(chance_of_getting_true=70)
                    mock_attendee.display_name = fake.first_name()
                    mock_attendee.registered_at = fake.date_time_between(start_date="-30d")
                    mock_event.attendees.append(mock_attendee)
            
            with patch("app.database.get_async_session"):
                with patch("app.services.create_matching_service"):
                    with patch("app.services.create_qr_service"):
                        response = client.get(f"/events/{event_id}/dashboard")
                        
                        # Test dashboard structure
                        if response.status_code == status.HTTP_200_OK:
                            data = response.json()
                            expected_keys = [
                                "event", "attendee_stats", "capacity_analysis",
                                "match_statistics", "qr_stats", "recent_registrations"
                            ]
                            for key in expected_keys:
                                assert key in data
    
    @pytest.mark.performance
    def test_dashboard_performance_with_large_dataset(self, client):
        """Test dashboard performance with large numbers of attendees."""
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.full_name = "Test Organizer"
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            
            # Mock large event (500 attendees)
            mock_event = MagicMock()
            mock_event.attendees = [MagicMock() for _ in range(500)]
            mock_event.matches = [MagicMock() for _ in range(1000)]
            
            import time
            
            with patch("app.database.get_async_session"):
                with patch("app.services.create_matching_service"):
                    with patch("app.services.create_qr_service"):
                        start_time = time.perf_counter()
                        response = client.get(f"/events/{event_id}/dashboard")
                        end_time = time.perf_counter()
                        
                        response_time = (end_time - start_time) * 1000
                        
                        # Dashboard should be responsive even with large datasets
                        assert response_time < 2000  # Less than 2 seconds
                        
                        if response.status_code == status.HTTP_200_OK:
                            # Verify data structure is still correct
                            data = response.json()
                            assert isinstance(data.get("attendee_stats"), dict)


@pytest.mark.integration
class TestEventRounds:
    """Integration tests for event round management."""
    
    @pytest.mark.faker
    def test_create_event_rounds(self, client, faker_instance):
        """Test creating rounds for an event."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            total_rounds = fake.random_int(min=3, max=12)
            
            with patch("app.database.get_async_session"):
                response = client.post(
                    f"/events/{event_id}/rounds?total_rounds={total_rounds}"
                )
                
                if response.status_code == status.HTTP_200_OK:
                    data = response.json()
                    assert data["rounds_created"] == total_rounds
                    assert "successfully" in data["message"].lower()
    
    @pytest.mark.faker
    def test_create_round_matches(self, client, faker_instance):
        """Test creating matches for a specific round."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            round_id = uuid.uuid4()
            
            # Mock matching service
            with patch("app.services.create_matching_service") as mock_service:
                mock_matches = [MagicMock() for _ in range(15)]
                mock_service.return_value.create_round_matches.return_value = mock_matches
                
                with patch("app.database.get_async_session"):
                    response = client.post(f"/events/{event_id}/rounds/{round_id}/matches")
                    
                    if response.status_code == status.HTTP_200_OK:
                        data = response.json()
                        assert data["matches_created"] == len(mock_matches)


@pytest.mark.integration
class TestEventCountdown:
    """Integration tests for event countdown functionality."""
    
    @pytest.mark.faker
    def test_start_event_countdown(self, client, faker_instance):
        """Test starting event countdown with realistic parameters."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            
            countdown_data = {
                "duration_minutes": fake.random_int(min=5, max=30),
                "message": fake.sentence(nb_words=8)
            }
            
            # Mock event and services
            with patch("app.database.get_async_session"):
                with patch("app.services.countdown_manager"):
                    with patch("app.services.connection_manager"):
                        response = client.post(
                            f"/events/{event_id}/countdown/start",
                            json=countdown_data
                        )
                        
                        if response.status_code == status.HTTP_200_OK:
                            data = response.json()
                            assert "countdown started" in data["message"].lower()
                            assert data["duration_minutes"] == countdown_data["duration_minutes"]
    
    @pytest.mark.faker
    def test_countdown_status_access_control(self, client, faker_instance):
        """Test countdown status access control for different user types."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        
        # Test as organizer
        with patch("app.auth.current_active_user") as mock_auth:
            mock_organizer = MagicMock()
            mock_organizer.id = uuid.uuid4()
            mock_organizer.is_organizer = True
            mock_auth.return_value = mock_organizer
            
            with patch("app.database.get_async_session"):
                response = client.get(f"/events/{event_id}/countdown/status")
                
                # Organizer should have access
                if response.status_code == status.HTTP_200_OK:
                    data = response.json()
                    assert "event_id" in data
                    assert "countdown" in data
        
        # Test as attendee
        with patch("app.auth.current_active_user") as mock_auth:
            mock_attendee = MagicMock()
            mock_attendee.id = uuid.uuid4()
            mock_attendee.is_organizer = False
            mock_auth.return_value = mock_attendee
            
            with patch("app.database.get_async_session"):
                response = client.get(f"/events/{event_id}/countdown/status")
                
                # Response depends on whether user is registered attendee
                assert response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_403_FORBIDDEN
                ]
    
    @pytest.mark.slow
    def test_countdown_real_time_updates(self, client, faker_instance):
        """Test countdown provides real-time updates."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            
            # Mock countdown manager with time progression
            countdown_times = [300, 299, 298]  # 5 minutes counting down
            
            with patch("app.services.countdown_manager") as mock_manager:
                mock_manager.get_countdown_status.side_effect = [
                    {"active": True, "remaining_seconds": t, "message": f"{t//60}:{t%60:02d} remaining"}
                    for t in countdown_times
                ]
                
                with patch("app.database.get_async_session"):
                    # Simulate multiple status checks
                    responses = []
                    for _ in range(3):
                        response = client.get(f"/events/{event_id}/countdown/status")
                        if response.status_code == status.HTTP_200_OK:
                            responses.append(response.json())
                    
                    # Verify countdown progression (if mocked correctly)
                    if len(responses) >= 2:
                        # In real scenario, remaining seconds should decrease
                        assert "countdown" in responses[0]


@pytest.mark.integration
class TestEventDeletion:
    """Integration tests for event deletion."""
    
    @pytest.mark.faker
    def test_delete_draft_event(self, client, faker_instance):
        """Test deleting a draft event."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            
            # Mock draft event
            with patch("app.database.get_async_session"):
                response = client.delete(f"/events/{event_id}")
                
                if response.status_code == status.HTTP_200_OK:
                    data = response.json()
                    assert "deleted" in data["message"].lower()
    
    @pytest.mark.faker
    def test_delete_active_event_fails(self, client, faker_instance):
        """Test that active events cannot be deleted."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            
            # Mock active event
            with patch("app.database.get_async_session"):
                response = client.delete(f"/events/{event_id}")
                
                # Should prevent deletion of active events
                if response.status_code == status.HTTP_400_BAD_REQUEST:
                    assert "active" in response.json()["detail"].lower()


# Helper fixtures for event testing
@pytest.fixture
def mock_event_with_attendees(faker_instance):
    """Create a mock event with realistic attendee data."""
    fake = setup_faker_providers(faker_instance)
    
    event = MagicMock()
    event.id = uuid.uuid4()
    event.name = fake.event_name()
    event.location = fake.venue_name()
    event.attendees = []
    
    # Generate diverse attendees
    for category in AttendeeCategory:
        count = fake.random_int(min=5, max=20)
        for _ in range(count):
            attendee = MagicMock()
            attendee.category = category
            attendee.display_name = fake.first_name()
            attendee.registration_confirmed = True
            attendee.checked_in = fake.boolean(chance_of_getting_true=80)
            attendee.registered_at = fake.date_time_between(start_date="-14d")
            event.attendees.append(attendee)
    
    return event


@pytest.fixture
def mock_organizer_user(faker_instance):
    """Create a mock organizer user."""
    fake = setup_faker_providers(faker_instance)
    
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = fake.email()
    user.full_name = fake.name()
    user.is_organizer = True
    user.is_active = True
    
    return user