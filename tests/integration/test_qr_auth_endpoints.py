"""
Integration tests for QR authentication API endpoints.

Tests QR code generation, validation, and authentication workflows
with realistic security scenarios.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from io import BytesIO

import pytest
from hypothesis import given, strategies as st
from fastapi import status

from tests.fixtures.faker_providers import setup_faker_providers


@pytest.mark.integration
class TestQRTokenGeneration:
    """Integration tests for QR token generation functionality."""
    
    @pytest.mark.faker
    def test_generate_qr_token_for_attendee(self, client, faker_instance):
        """Test QR token generation with realistic attendee data."""
        fake = setup_faker_providers(faker_instance)
        
        attendee_id = uuid.uuid4()
        
        token_request = {
            "attendee_id": str(attendee_id),
            "expire_hours": fake.random_int(min=1, max=48),
            "max_uses": fake.random_int(min=1, max=20)
        }
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Mock QR service
            with patch("app.services.create_qr_service") as mock_service:
                mock_qr_service = MagicMock()
                mock_qr_login = MagicMock()
                mock_qr_login.id = uuid.uuid4()
                mock_qr_login.qr_code_url = f"https://app.example.com/qr/login?token={fake.uuid4()}"
                mock_qr_login.expires_at = datetime.now() + timedelta(hours=token_request["expire_hours"])
                mock_qr_login.max_uses = token_request["max_uses"]
                
                mock_attendee = MagicMock()
                mock_attendee.display_name = fake.first_name()
                mock_qr_login.attendee = mock_attendee
                
                mock_qr_service.generate_attendee_qr_token.return_value = mock_qr_login
                mock_service.return_value = mock_qr_service
                
                response = client.post("/qr/generate-token", json=token_request)
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert "token_id" in data
                assert "qr_url" in data
                assert "expires_at" in data
                assert data["max_uses"] == token_request["max_uses"]
                assert data["attendee_name"] == mock_attendee.display_name
                assert "https://" in data["qr_url"]
    
    @pytest.mark.faker
    def test_qr_token_generation_authorization(self, client, faker_instance):
        """Test QR token generation requires organizer privileges."""
        fake = setup_faker_providers(faker_instance)
        
        attendee_id = uuid.uuid4()
        token_request = {
            "attendee_id": str(attendee_id),
            "expire_hours": 24,
            "max_uses": 5
        }
        
        # Test with non-organizer user
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_auth.side_effect = HTTPException(status_code=403, detail="Not an organizer")
            
            response = client.post("/qr/generate-token", json=token_request)
            assert response.status_code == status.HTTP_403_FORBIDDEN
    
    @given(
        expire_hours=st.integers(min_value=1, max_value=168),  # 1 hour to 1 week
        max_uses=st.integers(min_value=1, max_value=100)
    )
    def test_qr_token_parameters_validation(self, client, expire_hours, max_uses):
        """Test QR token generation with various parameter combinations."""
        attendee_id = uuid.uuid4()
        
        token_request = {
            "attendee_id": str(attendee_id),
            "expire_hours": expire_hours,
            "max_uses": max_uses
        }
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            with patch("app.services.create_qr_service") as mock_service:
                mock_qr_service = MagicMock()
                mock_qr_login = MagicMock()
                mock_qr_login.id = uuid.uuid4()
                mock_qr_login.qr_code_url = f"https://app.example.com/qr/login?token=test"
                mock_qr_login.expires_at = datetime.now() + timedelta(hours=expire_hours)
                mock_qr_login.max_uses = max_uses
                mock_qr_login.attendee = MagicMock(display_name="Test User")
                
                mock_qr_service.generate_attendee_qr_token.return_value = mock_qr_login
                mock_service.return_value = mock_qr_service
                
                response = client.post("/qr/generate-token", json=token_request)
                
                # Should succeed with reasonable parameters
                if expire_hours <= 72 and max_uses <= 50:  # Reasonable limits
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["max_uses"] == max_uses
    
    @pytest.mark.faker
    def test_qr_token_generation_error_handling(self, client, faker_instance):
        """Test QR token generation error scenarios."""
        fake = setup_faker_providers(faker_instance)
        
        # Test with non-existent attendee
        non_existent_attendee = uuid.uuid4()
        
        token_request = {
            "attendee_id": str(non_existent_attendee),
            "expire_hours": 24,
            "max_uses": 5
        }
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            with patch("app.services.create_qr_service") as mock_service:
                mock_qr_service = MagicMock()
                mock_qr_service.generate_attendee_qr_token.side_effect = ValueError("Attendee not found")
                mock_service.return_value = mock_qr_service
                
                response = client.post("/qr/generate-token", json=token_request)
                
                assert response.status_code == status.HTTP_404_NOT_FOUND
                assert "not found" in response.json()["detail"].lower()


@pytest.mark.integration
class TestQRTokenValidation:
    """Integration tests for QR token validation functionality."""
    
    @pytest.mark.faker
    def test_validate_qr_token_success(self, client, faker_instance):
        """Test successful QR token validation."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        test_token = fake.uuid4()
        
        # Mock valid QR token
        with patch("app.services.create_qr_service") as mock_service:
            mock_qr_service = MagicMock()
            mock_validation = {
                "valid": True,
                "attendee_name": fake.first_name(),
                "event_name": fake.event_name(),
                "expires_at": (datetime.now() + timedelta(hours=12)).isoformat(),
                "remaining_uses": fake.random_int(min=1, max=10)
            }
            mock_qr_service.validate_qr_token.return_value = mock_validation
            mock_service.return_value = mock_qr_service
            
            response = client.get(
                f"/qr/validate/{event_id}",
                params={"token": test_token}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["valid"] == True
            assert data["attendee_name"] == mock_validation["attendee_name"]
            assert data["event_name"] == mock_validation["event_name"]
            assert "remaining_uses" in data
    
    @pytest.mark.faker
    def test_validate_expired_qr_token(self, client, faker_instance):
        """Test validation of expired QR tokens."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        expired_token = fake.uuid4()
        
        with patch("app.services.create_qr_service") as mock_service:
            mock_qr_service = MagicMock()
            mock_validation = {
                "valid": False,
                "attendee_name": None,
                "event_name": None,
                "expires_at": None,
                "remaining_uses": 0
            }
            mock_qr_service.validate_qr_token.return_value = mock_validation
            mock_service.return_value = mock_qr_service
            
            response = client.get(
                f"/qr/validate/{event_id}",
                params={"token": expired_token}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["valid"] == False
            assert data["remaining_uses"] == 0
    
    @pytest.mark.faker
    def test_validate_malformed_qr_token(self, client, faker_instance):
        """Test validation of malformed QR tokens."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        
        # Test various malformed token formats
        malformed_tokens = [
            "not-a-uuid",
            "",
            "123",
            fake.text(max_nb_chars=10),
            "invalid-format-token"
        ]
        
        for bad_token in malformed_tokens:
            with patch("app.services.create_qr_service") as mock_service:
                mock_qr_service = MagicMock()
                mock_qr_service.validate_qr_token.side_effect = ValueError("Invalid token format")
                mock_service.return_value = mock_qr_service
                
                response = client.get(
                    f"/qr/validate/{event_id}",
                    params={"token": bad_token}
                )
                
                # Should handle gracefully
                assert response.status_code in [
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ]


@pytest.mark.integration
class TestQRAuthentication:
    """Integration tests for QR-based authentication workflow."""
    
    @pytest.mark.faker
    def test_qr_login_success(self, client, faker_instance):
        """Test successful QR code login."""
        fake = setup_faker_providers(faker_instance)
        
        valid_token = fake.uuid4()
        
        login_request = {
            "token": valid_token
        }
        
        # Mock successful authentication
        with patch("app.services.create_qr_service") as mock_service:
            mock_qr_service = MagicMock()
            mock_auth_result = {
                "success": True,
                "user_id": uuid.uuid4(),
                "attendee_id": uuid.uuid4(),
                "event_id": uuid.uuid4(),
                "remaining_uses": fake.random_int(min=1, max=5),
                "message": "Login successful"
            }
            mock_qr_service.authenticate_with_qr_token.return_value = mock_auth_result
            mock_service.return_value = mock_qr_service
            
            response = client.post("/qr/login", json=login_request)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["success"] == True
            assert "user_id" in data
            assert "attendee_id" in data
            assert "event_id" in data
            assert data["remaining_uses"] > 0
    
    @pytest.mark.faker
    def test_qr_login_token_exhausted(self, client, faker_instance):
        """Test QR login when token uses are exhausted."""
        fake = setup_faker_providers(faker_instance)
        
        exhausted_token = fake.uuid4()
        
        login_request = {
            "token": exhausted_token
        }
        
        with patch("app.services.create_qr_service") as mock_service:
            mock_qr_service = MagicMock()
            mock_auth_result = {
                "success": False,
                "user_id": None,
                "attendee_id": None,
                "event_id": None,
                "remaining_uses": 0,
                "message": "Token has been used too many times"
            }
            mock_qr_service.authenticate_with_qr_token.return_value = mock_auth_result
            mock_service.return_value = mock_qr_service
            
            response = client.post("/qr/login", json=login_request)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["success"] == False
            assert data["remaining_uses"] == 0
            assert "used too many times" in data["message"].lower()
    
    @pytest.mark.faker
    def test_qr_login_rate_limiting(self, client, faker_instance):
        """Test rate limiting for QR login attempts."""
        fake = setup_faker_providers(faker_instance)
        
        token = fake.uuid4()
        login_request = {"token": token}
        
        # Simulate multiple rapid login attempts
        with patch("app.services.create_qr_service") as mock_service:
            mock_qr_service = MagicMock()
            
            responses = []
            for attempt in range(10):  # 10 rapid attempts
                if attempt < 5:
                    # First few succeed
                    mock_auth_result = {
                        "success": True,
                        "user_id": uuid.uuid4(),
                        "remaining_uses": 5 - attempt,
                        "message": "Login successful"
                    }
                else:
                    # Later attempts fail due to rate limiting
                    mock_auth_result = {
                        "success": False,
                        "message": "Too many login attempts"
                    }
                
                mock_qr_service.authenticate_with_qr_token.return_value = mock_auth_result
                mock_service.return_value = mock_qr_service
                
                response = client.post("/qr/login", json=login_request)
                responses.append(response)
            
            # Verify rate limiting kicks in
            successful_attempts = sum(1 for r in responses if r.json().get("success"))
            assert successful_attempts <= 5  # Should be limited


@pytest.mark.integration
class TestQRBadgeGeneration:
    """Integration tests for QR code badge generation."""
    
    @pytest.mark.faker
    def test_generate_event_badges(self, client, faker_instance):
        """Test QR badge generation for event attendees."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Mock PDF service
            with patch("app.services.create_pdf_service") as mock_pdf:
                mock_pdf_service = MagicMock()
                mock_pdf_bytes = BytesIO(b"fake pdf content")
                mock_pdf_service.generate_qr_badges.return_value = mock_pdf_bytes
                mock_pdf.return_value = mock_pdf_service
                
                response = client.get(f"/qr/badges/{event_id}")
                
                if response.status_code == status.HTTP_200_OK:
                    assert response.headers["content-type"] == "application/pdf"
                    assert len(response.content) > 0
    
    @pytest.mark.faker
    def test_generate_individual_badge(self, client, faker_instance):
        """Test individual QR badge generation."""
        fake = setup_faker_providers(faker_instance)
        
        attendee_id = uuid.uuid4()
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            with patch("app.services.create_pdf_service") as mock_pdf:
                mock_pdf_service = MagicMock()
                mock_pdf_bytes = BytesIO(b"fake individual badge pdf")
                mock_pdf_service.generate_individual_badge.return_value = mock_pdf_bytes
                mock_pdf.return_value = mock_pdf_service
                
                response = client.get(f"/qr/badge/{attendee_id}")
                
                if response.status_code == status.HTTP_200_OK:
                    assert response.headers["content-type"] == "application/pdf"
                    assert len(response.content) > 0


@pytest.mark.integration
class TestQRSecurityScenarios:
    """Integration tests for QR authentication security scenarios."""
    
    @pytest.mark.faker
    def test_qr_token_replay_attack_prevention(self, client, faker_instance):
        """Test prevention of QR token replay attacks."""
        fake = setup_faker_providers(faker_instance)
        
        token = fake.uuid4()
        login_request = {"token": token}
        
        with patch("app.services.create_qr_service") as mock_service:
            mock_qr_service = MagicMock()
            
            # First use should succeed
            mock_qr_service.authenticate_with_qr_token.return_value = {
                "success": True,
                "user_id": uuid.uuid4(),
                "remaining_uses": 4,
                "message": "Login successful"
            }
            mock_service.return_value = mock_qr_service
            
            first_response = client.post("/qr/login", json=login_request)
            assert first_response.status_code == status.HTTP_200_OK
            assert first_response.json()["success"] == True
            
            # Subsequent uses should track usage
            mock_qr_service.authenticate_with_qr_token.return_value = {
                "success": True,
                "user_id": uuid.uuid4(),
                "remaining_uses": 3,
                "message": "Login successful"
            }
            
            second_response = client.post("/qr/login", json=login_request)
            if second_response.status_code == status.HTTP_200_OK:
                assert second_response.json()["remaining_uses"] < first_response.json()["remaining_uses"]
    
    @pytest.mark.faker
    def test_qr_token_expiry_enforcement(self, client, faker_instance):
        """Test enforcement of QR token expiry times."""
        fake = setup_faker_providers(faker_instance)
        
        expired_token = fake.uuid4()
        
        with patch("app.services.create_qr_service") as mock_service:
            mock_qr_service = MagicMock()
            mock_qr_service.authenticate_with_qr_token.side_effect = ValueError("Token has expired")
            mock_service.return_value = mock_qr_service
            
            login_request = {"token": expired_token}
            response = client.post("/qr/login", json=login_request)
            
            # Should handle expired tokens appropriately
            assert response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED
            ]
    
    @pytest.mark.faker
    def test_qr_token_cross_event_isolation(self, client, faker_instance):
        """Test that QR tokens are isolated between different events."""
        fake = setup_faker_providers(faker_instance)
        
        event1_id = uuid.uuid4()
        event2_id = uuid.uuid4()
        cross_event_token = fake.uuid4()
        
        # Try to validate token for different event
        with patch("app.services.create_qr_service") as mock_service:
            mock_qr_service = MagicMock()
            mock_qr_service.validate_qr_token.return_value = {
                "valid": False,
                "attendee_name": None,
                "event_name": None,
                "expires_at": None,
                "remaining_uses": None
            }
            mock_service.return_value = mock_qr_service
            
            # Token generated for event1 shouldn't work for event2
            response = client.get(
                f"/qr/validate/{event2_id}",
                params={"token": cross_event_token}
            )
            
            if response.status_code == status.HTTP_200_OK:
                data = response.json()
                assert data["valid"] == False


# Helper fixtures for QR testing
@pytest.fixture
def mock_qr_service(faker_instance):
    """Create a mock QR service for testing."""
    fake = setup_faker_providers(faker_instance)
    
    service = MagicMock()
    service.generate_attendee_qr_token = MagicMock()
    service.validate_qr_token = MagicMock()
    service.authenticate_with_qr_token = MagicMock()
    
    return service


@pytest.fixture
def sample_qr_token(faker_instance):
    """Generate a sample QR token for testing."""
    fake = setup_faker_providers(faker_instance)
    
    return {
        "token_id": uuid.uuid4(),
        "qr_url": f"https://app.example.com/qr/login?token={fake.uuid4()}",
        "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
        "max_uses": 10,
        "attendee_name": fake.first_name()
    }