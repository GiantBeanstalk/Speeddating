"""
Fuzzing tests for database operations and ORM security.

Tests database layer resilience against malformed queries,
injection attacks, and boundary conditions.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys

import pytest
from hypothesis import given, strategies as st, settings, assume
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from fastapi import status

from app.models import AttendeeCategory, EventStatus, MatchResponse
from tests.fixtures.faker_providers import setup_faker_providers


@st.composite
def database_injection_strategy(draw):
    """Generate database injection attack patterns."""
    injection_types = [
        "sql_injection_basic",
        "sql_injection_union", 
        "sql_injection_blind",
        "sql_injection_time",
        "nosql_injection",
        "orm_injection"
    ]
    
    injection_type = draw(st.sampled_from(injection_types))
    
    patterns = {
        "sql_injection_basic": [
            "'; DROP TABLE users CASCADE; --",
            "'; DELETE FROM events; --",
            "'; UPDATE users SET is_superuser=true; --",
            "1' OR '1'='1' --",
            "admin'--",
            "'; EXEC xp_cmdshell('dir'); --"
        ],
        "sql_injection_union": [
            "' UNION SELECT password FROM users --",
            "' UNION SELECT 1,2,3,4,5,6,7,8,9,10 --",
            "' UNION ALL SELECT schema_name FROM information_schema.schemata --",
            "' UNION SELECT table_name FROM information_schema.tables --"
        ],
        "sql_injection_blind": [
            "' AND (SELECT COUNT(*) FROM users) > 0 --",
            "' AND LENGTH(password) > 5 --",
            "' AND SUBSTRING(password,1,1) = 'a' --",
            "' AND ASCII(SUBSTRING(password,1,1)) > 64 --"
        ],
        "sql_injection_time": [
            "'; WAITFOR DELAY '00:00:05' --",
            "'; SELECT SLEEP(5) --",
            "'; pg_sleep(5) --",
            "' AND (SELECT * FROM (SELECT COUNT(*),CONCAT(version(),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a) --"
        ],
        "nosql_injection": [
            "'; return true; //",
            "$where: '1 == 1'",
            "'; return this.password.match(/.*/) //",
            "$ne: null",
            "$gt: ''",
            "$regex: '.*'"
        ],
        "orm_injection": [
            "__class__.__bases__[0].__subclasses__()[104]",
            "{{config.__class__.__init__.__globals__}}",
            "{{request.application.__globals__}}",
            "__import__('os').system('ls')",
            "eval('__import__(\"os\").system(\"ls\")')"
        ]
    }
    
    return draw(st.sampled_from(patterns[injection_type]))


@st.composite
def database_constraint_violation_strategy(draw):
    """Generate data that violates database constraints."""
    violation_type = draw(st.sampled_from([
        "foreign_key_violation",
        "unique_constraint_violation", 
        "not_null_violation",
        "check_constraint_violation",
        "data_type_violation"
    ]))
    
    if violation_type == "foreign_key_violation":
        return {"user_id": uuid.uuid4(), "event_id": uuid.uuid4()}
    elif violation_type == "unique_constraint_violation":
        return {"email": "duplicate@example.com"}
    elif violation_type == "not_null_violation":
        return {"required_field": None}
    elif violation_type == "check_constraint_violation":
        return {"age": draw(st.integers(min_value=-100, max_value=0))}
    else:  # data_type_violation
        return {"numeric_field": "not_a_number", "date_field": "not_a_date"}


@pytest.mark.fuzzing
class TestDatabaseInjectionFuzzing:
    """Fuzzing tests for SQL injection prevention."""
    
    @given(injection_payload=database_injection_strategy())
    @settings(max_examples=50, deadline=10000)
    def test_sql_injection_in_search_queries(self, client, injection_payload):
        """Fuzz search functionality for SQL injection vulnerabilities."""
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Test injection in search parameters
            search_params = {
                "search": injection_payload,
                "filter": injection_payload,
                "order_by": injection_payload
            }
            
            try:
                response = client.get("/events/", params=search_params)
                
                # Should handle injection attempts gracefully
                assert response.status_code in [
                    status.HTTP_200_OK,
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ]
                
                # Should not return SQL error messages
                if response.status_code == status.HTTP_200_OK:
                    response_text = response.text.lower()
                    sql_errors = [
                        "syntax error", "sql", "database error", "constraint",
                        "foreign key", "duplicate key", "postgresql", "mysql"
                    ]
                    for error in sql_errors:
                        assert error not in response_text, f"SQL error exposed: {error}"
                        
            except Exception as e:
                pytest.fail(f"Unhandled exception with injection payload: {e}")
    
    @given(injection_payload=database_injection_strategy())
    @settings(max_examples=30, deadline=8000)
    def test_sql_injection_in_attendee_registration(self, client, injection_payload):
        """Fuzz attendee registration for SQL injection vulnerabilities."""
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            registration_data = {
                "display_name": injection_payload,
                "category": AttendeeCategory.SINGLE_WOMAN.value,
                "contact_email": f"test{injection_payload}@example.com",
                "public_bio": injection_payload,
                "dietary_requirements": injection_payload
            }
            
            try:
                response = client.post(
                    f"/attendees/register/{event_id}",
                    json=registration_data
                )
                
                # Should prevent SQL injection
                assert response.status_code in [
                    status.HTTP_201_CREATED,
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    status.HTTP_404_NOT_FOUND  # Event not found
                ]
                
                # Check for SQL injection success indicators
                if response.status_code == status.HTTP_201_CREATED:
                    response_data = response.json()
                    
                    # Injection payload should be sanitized
                    for field, value in response_data.items():
                        if isinstance(value, str) and injection_payload in value:
                            # Should not contain dangerous SQL patterns
                            dangerous_patterns = ["DROP TABLE", "DELETE FROM", "UNION SELECT"]
                            for pattern in dangerous_patterns:
                                assert pattern.upper() not in value.upper()
                                
            except SQLAlchemyError:
                # Database errors are acceptable - ORM should catch them
                pass
            except Exception as e:
                pytest.fail(f"Unhandled exception: {e}")
    
    @given(
        field_name=st.sampled_from(["name", "location", "description"]),
        injection_payload=database_injection_strategy()
    )
    @settings(max_examples=25, deadline=6000)
    def test_sql_injection_in_event_operations(self, client, field_name, injection_payload):
        """Fuzz event operations for SQL injection vulnerabilities."""
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Test event creation with injection payload
            event_data = {
                "name": "Test Event",
                "event_date": (datetime.now() + timedelta(days=7)).isoformat(),
                "max_attendees": 50,
                "min_attendees": 10,
                field_name: injection_payload
            }
            
            try:
                response = client.post("/events/", json=event_data)
                
                # Should handle injection attempts
                assert response.status_code in [
                    status.HTTP_201_CREATED,
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ]
                
                # Test event update with injection payload
                if response.status_code == status.HTTP_201_CREATED:
                    event_id = response.json()["id"]
                    update_data = {field_name: injection_payload}
                    
                    update_response = client.put(f"/events/{event_id}", json=update_data)
                    assert update_response.status_code in [
                        status.HTTP_200_OK,
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_404_NOT_FOUND
                    ]
                    
            except SQLAlchemyError:
                pass  # Database errors are handled by the ORM
            except Exception as e:
                pytest.fail(f"Unhandled exception: {e}")


@pytest.mark.fuzzing
class TestDatabaseConstraintFuzzing:
    """Fuzzing tests for database constraint handling."""
    
    @given(constraint_violation=database_constraint_violation_strategy())
    @settings(max_examples=30, deadline=6000)
    def test_constraint_violation_handling(self, client, constraint_violation):
        """Test handling of database constraint violations."""
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Create event data with potential constraint violations
            base_event_data = {
                "name": "Test Event",
                "event_date": (datetime.now() + timedelta(days=7)).isoformat(),
                "max_attendees": 50,
                "min_attendees": 10
            }
            
            # Merge constraint violation data
            event_data = {**base_event_data, **constraint_violation}
            
            try:
                response = client.post("/events/", json=event_data)
                
                # Should handle constraint violations gracefully
                if "user_id" in constraint_violation or "event_id" in constraint_violation:
                    # Foreign key violations should be handled
                    assert response.status_code in [
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_422_UNPROCESSABLE_ENTITY,
                        status.HTTP_404_NOT_FOUND
                    ]
                elif constraint_violation.get("age", 0) < 0:
                    # Invalid age should be rejected
                    assert response.status_code in [
                        status.HTTP_400_BAD_REQUEST,
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ]
                    
            except IntegrityError:
                # Database integrity errors should be caught by the application
                pass
            except Exception as e:
                pytest.fail(f"Unhandled constraint violation: {e}")
    
    @given(
        batch_size=st.integers(min_value=1, max_value=1000),
        duplicate_probability=st.floats(min_value=0.1, max_value=0.9)
    )
    @settings(max_examples=15, deadline=10000)
    def test_bulk_operation_constraint_handling(self, client, batch_size, duplicate_probability, faker_instance):
        """Test constraint handling in bulk database operations."""
        fake = setup_faker_providers(faker_instance)
        
        # Simulate bulk attendee registration with potential duplicates
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            
            # Generate attendee data with potential duplicates
            attendees_data = []
            base_email = fake.email()
            
            for i in range(min(batch_size, 50)):  # Limit to reasonable size for testing
                # Sometimes use duplicate email to trigger constraint violation
                if fake.random.random() < duplicate_probability:
                    email = base_email  # Duplicate email
                else:
                    email = fake.email()  # Unique email
                
                attendee_data = {
                    "display_name": fake.first_name(),
                    "category": fake.random_element(AttendeeCategory).value,
                    "contact_email": email
                }
                attendees_data.append(attendee_data)
            
            # Submit bulk registrations
            successful_registrations = 0
            constraint_violations = 0
            
            for attendee_data in attendees_data:
                try:
                    response = client.post(
                        f"/attendees/register/{event_id}",
                        json=attendee_data
                    )
                    
                    if response.status_code == status.HTTP_201_CREATED:
                        successful_registrations += 1
                    elif response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]:
                        constraint_violations += 1
                        
                except Exception:
                    constraint_violations += 1
            
            # Should handle some registrations and some constraint violations
            total_processed = successful_registrations + constraint_violations
            assert total_processed >= batch_size * 0.5, "Too many unhandled errors in bulk operation"


@pytest.mark.fuzzing
class TestDatabasePerformanceFuzzing:
    """Fuzzing tests for database performance under load."""
    
    @given(
        query_complexity=st.integers(min_value=1, max_value=100),
        concurrent_users=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=10, deadline=15000)
    def test_complex_query_performance(self, client, query_complexity, concurrent_users, faker_instance):
        """Test database performance with complex queries."""
        fake = setup_faker_providers(faker_instance)
        
        import concurrent.futures
        import time
        
        def make_complex_query():
            """Make a complex query to test database performance."""
            with patch("app.auth.current_active_organizer") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_user.is_organizer = True
                mock_auth.return_value = mock_user
                
                # Create complex query parameters
                complex_params = {
                    "limit": min(query_complexity, 100),
                    "offset": 0,
                    "search": fake.text(max_nb_chars=min(query_complexity * 2, 200)),
                    "status_filter": fake.random_element(EventStatus).value if fake.boolean() else None
                }
                
                start_time = time.perf_counter()
                response = client.get("/events/", params=complex_params)
                end_time = time.perf_counter()
                
                query_time = (end_time - start_time) * 1000  # Convert to ms
                return response, query_time
        
        # Execute concurrent complex queries
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(concurrent_users, 10)) as executor:
            futures = [executor.submit(make_complex_query) for _ in range(min(concurrent_users, 20))]
            results = [f.result() for f in futures]
        
        # Analyze performance results
        response_times = [result[1] for result in results if result[0].status_code == status.HTTP_200_OK]
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            # Database should handle complex queries reasonably
            assert avg_response_time < 5000, f"Average query time too high: {avg_response_time:.2f}ms"
            assert max_response_time < 10000, f"Max query time too high: {max_response_time:.2f}ms"
    
    @pytest.mark.slow
    def test_database_connection_exhaustion(self, client, faker_instance):
        """Test database behavior under connection exhaustion."""
        fake = setup_faker_providers(faker_instance)
        
        import concurrent.futures
        
        def make_database_request():
            """Make a request that uses database connection."""
            with patch("app.auth.current_active_organizer") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_user.is_organizer = True
                mock_auth.return_value = mock_user
                
                return client.get("/events/")
        
        # Try to exhaust database connections
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_database_request) for _ in range(100)]
            results = [f.result() for f in futures]
        
        # System should handle connection pressure gracefully
        successful_requests = [r for r in results if r.status_code == status.HTTP_200_OK]
        server_errors = [r for r in results if r.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR]
        
        # Should not have too many server errors
        success_rate = len(successful_requests) / len(results)
        assert success_rate >= 0.7, f"Too many failures under load: {success_rate:.2%}"


@pytest.mark.fuzzing
class TestDatabaseTransactionFuzzing:
    """Fuzzing tests for database transaction integrity."""
    
    @given(
        operation_count=st.integers(min_value=2, max_value=20),
        failure_probability=st.floats(min_value=0.1, max_value=0.5)
    )
    @settings(max_examples=10, deadline=12000)
    def test_transaction_rollback_integrity(self, client, operation_count, failure_probability, faker_instance):
        """Test transaction rollback integrity under various failure scenarios."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Create an event first
            event_data = {
                "name": fake.event_name(),
                "event_date": (datetime.now() + timedelta(days=7)).isoformat(),
                "max_attendees": 50,
                "min_attendees": 10
            }
            
            event_response = client.post("/events/", json=event_data)
            if event_response.status_code != status.HTTP_201_CREATED:
                return  # Skip if event creation fails
                
            event_id = event_response.json()["id"]
            
            # Perform multiple operations with potential failures
            operations_attempted = 0
            operations_successful = 0
            
            for i in range(min(operation_count, 10)):  # Limit for performance
                # Randomly introduce failures
                if fake.random.random() < failure_probability:
                    # Attempt operation that should fail (invalid data)
                    invalid_data = {
                        "name": None,  # Invalid - should cause failure
                        "max_attendees": -1  # Invalid - should cause failure
                    }
                    response = client.put(f"/events/{event_id}", json=invalid_data)
                else:
                    # Valid operation
                    valid_data = {
                        "name": fake.event_name(),
                        "description": fake.text(max_nb_chars=100)
                    }
                    response = client.put(f"/events/{event_id}", json=valid_data)
                
                operations_attempted += 1
                
                if response.status_code == status.HTTP_200_OK:
                    operations_successful += 1
            
            # Verify final state is consistent
            final_response = client.get(f"/events/{event_id}")
            
            if final_response.status_code == status.HTTP_200_OK:
                # Event should still exist and be in valid state
                final_data = final_response.json()
                assert final_data["name"] is not None
                assert final_data["max_attendees"] > 0
                
    def test_concurrent_transaction_integrity(self, client, faker_instance):
        """Test transaction integrity under concurrent operations."""
        fake = setup_faker_providers(faker_instance)
        
        import concurrent.futures
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Create an event to be modified concurrently
            event_data = {
                "name": fake.event_name(),
                "event_date": (datetime.now() + timedelta(days=7)).isoformat(),
                "max_attendees": 100,
                "min_attendees": 10
            }
            
            event_response = client.post("/events/", json=event_data)
            if event_response.status_code != status.HTTP_201_CREATED:
                return
                
            event_id = event_response.json()["id"]
            
            def update_event(update_number):
                """Update event concurrently."""
                update_data = {
                    "name": f"Updated Event {update_number}",
                    "description": f"Updated by thread {update_number}"
                }
                return client.put(f"/events/{event_id}", json=update_data)
            
            # Perform concurrent updates
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(update_event, i) for i in range(10)]
                results = [f.result() for f in futures]
            
            # Verify final state is consistent
            final_response = client.get(f"/events/{event_id}")
            
            if final_response.status_code == status.HTTP_200_OK:
                final_data = final_response.json()
                # Event should exist and have valid data
                assert final_data["name"].startswith("Updated Event")
                assert "Updated by thread" in final_data.get("description", "")
            
            # Count successful updates
            successful_updates = [r for r in results if r.status_code == status.HTTP_200_OK]
            
            # Should handle concurrent updates without corruption
            assert len(successful_updates) >= 1, "No concurrent updates succeeded"


# Test utilities for database fuzzing
@pytest.fixture
def database_attack_vectors():
    """Database-specific attack vectors for fuzzing."""
    return {
        "sql_injection": [
            "'; DROP TABLE users; --",
            "' OR '1'='1' --", 
            "' UNION SELECT * FROM passwords --",
            "'; DELETE FROM events; --"
        ],
        "nosql_injection": [
            "$where: '1 == 1'",
            "$ne: null",
            "$gt: ''",
            "$regex: '.*'"
        ],
        "orm_injection": [
            "__class__.__bases__[0].__subclasses__()",
            "{{config.__class__.__init__.__globals__}}",
            "__import__('os').system('ls')"
        ]
    }