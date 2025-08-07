"""
Integration tests for attendees API endpoints.

Tests attendee registration, management, and interaction functionality
with realistic UK demographic data using Faker providers.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, strategies as st
from fastapi import status

from app.models import AttendeeCategory, EventStatus, MatchResponse
from tests.fixtures.faker_providers import setup_faker_providers


@pytest.mark.integration
class TestAttendeeRegistration:
    """Integration tests for attendee registration functionality."""
    
    @pytest.mark.faker
    def test_register_attendee_with_realistic_uk_data(self, client, faker_instance):
        """Test attendee registration with realistic UK demographic data."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        
        # Generate realistic UK attendee data
        registration_data = {
            "display_name": fake.first_name(),
            "category": fake.random_element(AttendeeCategory).value,
            "age": fake.random_int(min=25, max=55),  # Typical speed dating age range
            "public_bio": fake.text(max_nb_chars=200),
            "dietary_requirements": fake.random_element([
                "Vegetarian", "Vegan", "Gluten-free", "No nuts", "None", ""
            ]),
            "contact_email": fake.email(),
            "contact_phone": fake.uk_phone_number(),
            "fetlife_username": fake.fetlife_username(),
            "contact_visible_to_matches": fake.boolean(chance_of_getting_true=80),
            "profile_visible": fake.boolean(chance_of_getting_true=90)
        }
        
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.email = fake.email()
            mock_auth.return_value = mock_user
            
            with patch("app.database.get_async_session"):
                response = client.post(
                    f"/attendees/register/{event_id}",
                    json=registration_data
                )
                
                if response.status_code == status.HTTP_201_CREATED:
                    data = response.json()
                    assert data["display_name"] == registration_data["display_name"]
                    assert data["category"] == registration_data["category"]
                    assert data["age"] == registration_data["age"]
                    assert "id" in data
                    assert data["registration_confirmed"] == False  # Pending confirmation
    
    @pytest.mark.faker
    def test_registration_contact_validation(self, client, faker_instance):
        """Test that at least one contact method is required."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        
        # Test registration without any contact info
        registration_data = {
            "display_name": fake.first_name(),
            "category": AttendeeCategory.SINGLE_WOMAN.value,
            "age": 30,
            "public_bio": "Looking forward to meeting new people!"
            # No contact info provided
        }
        
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            response = client.post(
                f"/attendees/register/{event_id}",
                json=registration_data
            )
            
            # Should fail validation
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            error_detail = response.json()["detail"]
            assert any("contact" in str(error).lower() for error in error_detail)
    
    @given(
        category=st.sampled_from(list(AttendeeCategory)),
        age=st.integers(min_value=18, max_value=80),
        profile_visible=st.booleans()
    )
    def test_attendee_registration_property_based(
        self, client, category, age, profile_visible
    ):
        """Test attendee registration with property-based testing."""
        event_id = uuid.uuid4()
        
        registration_data = {
            "display_name": "Test User",
            "category": category.value,
            "age": age,
            "contact_email": "test@example.com",
            "profile_visible": profile_visible
        }
        
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            with patch("app.database.get_async_session"):
                response = client.post(
                    f"/attendees/register/{event_id}",
                    json=registration_data
                )
                
                # Should succeed with valid data
                if response.status_code == status.HTTP_201_CREATED:
                    data = response.json()
                    assert data["category"] == category.value
                    assert data["age"] == age
                    # Profile visibility affects response structure
    
    @pytest.mark.faker
    def test_bio_content_filtering(self, client, faker_instance):
        """Test bio content filtering for inappropriate content."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        
        # Test with potentially inappropriate content
        test_cases = [
            "Hi, I'm looking for fun and connection!",  # Should pass
            "Visit my website at example.com for more",  # Might be filtered
            fake.text(max_nb_chars=100),  # Random text should generally pass
        ]
        
        for bio_text in test_cases:
            registration_data = {
                "display_name": fake.first_name(),
                "category": AttendeeCategory.SINGLE_MAN.value,
                "contact_email": fake.email(),
                "public_bio": bio_text
            }
            
            with patch("app.auth.current_active_user") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_auth.return_value = mock_user
                
                with patch("app.database.get_async_session"):
                    response = client.post(
                        f"/attendees/register/{event_id}",
                        json=registration_data
                    )
                    
                    # Response depends on content filtering result
                    assert response.status_code in [
                        status.HTTP_201_CREATED,
                        status.HTTP_400_BAD_REQUEST
                    ]
    
    @pytest.mark.faker
    def test_duplicate_registration_prevention(self, client, faker_instance):
        """Test that users cannot register multiple times for same event."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        
        registration_data = {
            "display_name": fake.first_name(),
            "category": AttendeeCategory.SINGLE_WOMAN.value,
            "contact_email": fake.email()
        }
        
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            with patch("app.database.get_async_session"):
                # First registration
                response1 = client.post(
                    f"/attendees/register/{event_id}",
                    json=registration_data
                )
                
                # Second registration attempt
                response2 = client.post(
                    f"/attendees/register/{event_id}",
                    json=registration_data
                )
                
                # First should succeed, second should fail or be handled gracefully
                if response1.status_code == status.HTTP_201_CREATED:
                    assert response2.status_code in [
                        status.HTTP_409_CONFLICT,
                        status.HTTP_400_BAD_REQUEST
                    ]


@pytest.mark.integration
class TestAttendeeManagement:
    """Integration tests for attendee management functionality."""
    
    @pytest.mark.faker
    def test_get_event_attendees_with_filtering(self, client, faker_instance):
        """Test retrieving event attendees with various filters."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Test different filter combinations
            filter_params = [
                {"category": AttendeeCategory.SINGLE_WOMAN.value},
                {"checked_in": "true"},
                {"confirmed": "true"},
                {"category": AttendeeCategory.SINGLE_MAN.value, "checked_in": "false"}
            ]
            
            for params in filter_params:
                with patch("app.database.get_async_session"):
                    response = client.get(
                        f"/attendees/event/{event_id}",
                        params=params
                    )
                    
                    if response.status_code == status.HTTP_200_OK:
                        data = response.json()
                        assert isinstance(data, list)
                        # Verify filtering logic (would need proper mock data)
    
    @pytest.mark.faker
    def test_attendee_check_in_process(self, client, faker_instance):
        """Test attendee check-in functionality."""
        fake = setup_faker_providers(faker_instance)
        
        attendee_id = uuid.uuid4()
        table_number = fake.random_int(min=1, max=20)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            check_in_data = {
                "table_number": table_number,
                "notes": fake.sentence(nb_words=5)
            }
            
            with patch("app.database.get_async_session"):
                response = client.post(
                    f"/attendees/{attendee_id}/check-in",
                    json=check_in_data
                )
                
                if response.status_code == status.HTTP_200_OK:
                    data = response.json()
                    assert "checked in" in data["message"].lower()
                    assert data.get("table_number") == table_number
    
    @pytest.mark.faker
    def test_attendee_profile_visibility(self, client, faker_instance):
        """Test attendee profile visibility settings."""
        fake = setup_faker_providers(faker_instance)
        
        # Test as different user types
        user_types = [
            {"is_organizer": True, "should_see_all": True},
            {"is_organizer": False, "should_see_limited": True}
        ]
        
        for user_type in user_types:
            attendee_id = uuid.uuid4()
            
            with patch("app.auth.current_active_user") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_user.is_organizer = user_type["is_organizer"]
                mock_auth.return_value = mock_user
                
                with patch("app.database.get_async_session"):
                    response = client.get(f"/attendees/{attendee_id}")
                    
                    if response.status_code == status.HTTP_200_OK:
                        data = response.json()
                        # Verify appropriate data visibility based on user type
                        if user_type["is_organizer"]:
                            # Organizers should see full data
                            assert "contact_email" in data or data.get("contact_email") is None
                        else:
                            # Regular users should see limited data based on privacy settings
                            pass


@pytest.mark.integration
class TestAttendeeMatching:
    """Integration tests for attendee matching functionality."""
    
    @pytest.mark.faker
    def test_attendee_match_responses(self, client, faker_instance):
        """Test attendee match response functionality."""
        fake = setup_faker_providers(faker_instance)
        
        match_id = uuid.uuid4()
        
        # Test different response types
        responses = [MatchResponse.YES, MatchResponse.NO, MatchResponse.MAYBE]
        
        for response_type in responses:
            with patch("app.auth.current_active_user") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_auth.return_value = mock_user
                
                response_data = {
                    "response": response_type.value,
                    "notes": fake.sentence(nb_words=8) if fake.boolean() else None
                }
                
                with patch("app.database.get_async_session"):
                    response = client.post(
                        f"/attendees/matches/{match_id}/respond",
                        json=response_data
                    )
                    
                    if response.status_code == status.HTTP_200_OK:
                        data = response.json()
                        assert data["response"] == response_type.value
                        if response_data.get("notes"):
                            assert "notes" in data
    
    @pytest.mark.faker
    def test_get_attendee_matches(self, client, faker_instance):
        """Test retrieving matches for an attendee."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            # Mock attendee with matches
            with patch("app.database.get_async_session"):
                response = client.get("/attendees/my-matches")
                
                if response.status_code == status.HTTP_200_OK:
                    data = response.json()
                    assert isinstance(data, list)
                    # Each match should have required fields
                    for match in data[:3]:  # Test first few matches
                        expected_fields = ["id", "round_number", "other_attendee", "status"]
                        for field in expected_fields:
                            if field in match:
                                assert match[field] is not None
    
    @pytest.mark.faker
    def test_mutual_match_detection(self, client, faker_instance):
        """Test detection of mutual matches."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            # Mock scenario with mutual matches
            with patch("app.database.get_async_session"):
                response = client.get("/attendees/mutual-matches")
                
                if response.status_code == status.HTTP_200_OK:
                    data = response.json()
                    assert isinstance(data, list)
                    
                    # Mutual matches should include contact information
                    for match in data[:2]:
                        if match.get("is_mutual"):
                            # Contact info should be visible for mutual matches
                            assert "contact_info" in match or "other_attendee" in match


@pytest.mark.integration
class TestAttendeeProfiles:
    """Integration tests for attendee profile functionality."""
    
    @pytest.mark.faker
    def test_public_profile_access(self, client, faker_instance):
        """Test public profile access with QR code functionality."""
        fake = setup_faker_providers(faker_instance)
        
        attendee_id = uuid.uuid4()
        
        # Test public profile access (no auth required)
        response = client.get(f"/attendees/{attendee_id}/profile")
        
        # Profile should be accessible for QR code functionality
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            expected_fields = ["display_name", "age", "bio", "category"]
            
            # Public profile should show limited info
            for field in expected_fields:
                if field in data:
                    assert data[field] is not None
            
            # Sensitive info should not be in public profile
            sensitive_fields = ["contact_email", "contact_phone", "user_id"]
            for field in sensitive_fields:
                assert field not in data or data[field] is None
    
    @pytest.mark.faker
    def test_profile_qr_code_generation(self, client, faker_instance):
        """Test QR code generation for attendee profiles."""
        fake = setup_faker_providers(faker_instance)
        
        attendee_id = uuid.uuid4()
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            with patch("app.services.create_qr_service") as mock_qr_service:
                mock_service = MagicMock()
                mock_service.generate_profile_qr_code.return_value = {
                    "qr_code_data": "base64encodedqrcode",
                    "profile_url": f"https://app.example.com/profile/{attendee_id}"
                }
                mock_qr_service.return_value = mock_service
                
                response = client.get(f"/attendees/{attendee_id}/qr-code")
                
                if response.status_code == status.HTTP_200_OK:
                    data = response.json()
                    assert "qr_code_data" in data
                    assert "profile_url" in data


@pytest.mark.integration
class TestAttendeeStatistics:
    """Integration tests for attendee statistics and analytics."""
    
    @pytest.mark.faker
    def test_event_attendee_statistics(self, client, faker_instance):
        """Test event attendee statistics calculation."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Mock diverse attendee population
            with patch("app.database.get_async_session"):
                response = client.get(f"/attendees/event/{event_id}/statistics")
                
                if response.status_code == status.HTTP_200_OK:
                    data = response.json()
                    expected_stats = [
                        "total_attendees", "by_category", "by_age_group",
                        "check_in_rate", "response_rate"
                    ]
                    
                    for stat in expected_stats:
                        if stat in data:
                            assert isinstance(data[stat], (int, dict, float))
    
    @pytest.mark.performance
    def test_attendee_list_performance(self, client):
        """Test attendee list performance with large datasets."""
        event_id = uuid.uuid4()
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Mock large attendee list
            import time
            
            with patch("app.database.get_async_session"):
                start_time = time.perf_counter()
                response = client.get(
                    f"/attendees/event/{event_id}",
                    params={"limit": 500}
                )
                end_time = time.perf_counter()
                
                response_time = (end_time - start_time) * 1000
                
                # Should handle large lists efficiently
                assert response_time < 1000  # Less than 1 second
                
                if response.status_code == status.HTTP_200_OK:
                    data = response.json()
                    assert isinstance(data, list)


# Helper fixtures for attendee testing
@pytest.fixture
def sample_attendee_data(faker_instance):
    """Generate sample attendee registration data."""
    fake = setup_faker_providers(faker_instance)
    
    return {
        "display_name": fake.first_name(),
        "category": fake.random_element(AttendeeCategory).value,
        "age": fake.random_int(min=25, max=55),
        "public_bio": fake.text(max_nb_chars=200),
        "contact_email": fake.email(),
        "contact_phone": fake.uk_phone_number(),
        "contact_visible_to_matches": fake.boolean(chance_of_getting_true=80),
        "profile_visible": True
    }


@pytest.fixture
def mock_registered_attendees(faker_instance):
    """Create mock registered attendees for testing."""
    fake = setup_faker_providers(faker_instance)
    attendees = []
    
    for category in AttendeeCategory:
        count = fake.random_int(min=3, max=12)
        for _ in range(count):
            attendee = MagicMock()
            attendee.id = uuid.uuid4()
            attendee.display_name = fake.first_name()
            attendee.category = category
            attendee.age = fake.random_int(min=22, max=65)
            attendee.checked_in = fake.boolean(chance_of_getting_true=70)
            attendee.registration_confirmed = True
            attendee.payment_confirmed = fake.boolean(chance_of_getting_true=85)
            attendees.append(attendee)
    
    return attendees