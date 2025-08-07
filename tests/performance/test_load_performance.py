"""
Performance and load tests with realistic user scenarios.

Tests the application's performance under various load conditions
with realistic speed dating user workflows and data patterns.
"""

import uuid
import time
import asyncio
import statistics
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, strategies as st, settings

from app.models import AttendeeCategory, EventStatus
from tests.fixtures.faker_providers import setup_faker_providers


@pytest.mark.performance
class TestBasicPerformance:
    """Basic performance tests for individual operations."""
    
    @pytest.mark.faker
    def test_event_creation_performance(self, client, faker_instance):
        """Test performance of event creation operations."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_user.full_name = fake.name()
            mock_auth.return_value = mock_user
            
            # Measure event creation times
            creation_times = []
            event_count = 50
            
            for i in range(event_count):
                event_data = {
                    "name": fake.event_name(),
                    "description": fake.text(max_nb_chars=200),
                    "location": fake.venue_name(),
                    "event_date": fake.date_time_between(start_date="+1d", end_date="+30d").isoformat(),
                    "max_attendees": fake.random_int(min=20, max=100),
                    "min_attendees": fake.random_int(min=8, max=20),
                    "round_duration_minutes": fake.random_int(min=3, max=8),
                    "break_duration_minutes": fake.random_int(min=1, max=5)
                }
                
                start_time = time.perf_counter()
                response = client.post("/events/", json=event_data)
                end_time = time.perf_counter()
                
                creation_time = (end_time - start_time) * 1000  # Convert to ms
                creation_times.append(creation_time)
                
                # Verify successful creation (or expected failure)
                assert response.status_code in [201, 400, 422, 500]
            
            # Analyze performance
            avg_time = statistics.mean(creation_times)
            median_time = statistics.median(creation_times)
            p95_time = sorted(creation_times)[int(0.95 * len(creation_times))]
            
            # Performance assertions
            assert avg_time < 500, f"Average event creation time too high: {avg_time:.2f}ms"
            assert median_time < 300, f"Median event creation time too high: {median_time:.2f}ms"
            assert p95_time < 1000, f"95th percentile too high: {p95_time:.2f}ms"
            
            print(f"Event creation performance:")
            print(f"  Average: {avg_time:.2f}ms")
            print(f"  Median: {median_time:.2f}ms")
            print(f"  95th percentile: {p95_time:.2f}ms")
    
    @pytest.mark.faker
    def test_attendee_registration_performance(self, client, faker_instance):
        """Test performance of attendee registration operations."""
        fake = setup_faker_providers(faker_instance)
        
        with patch("app.auth.current_active_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_auth.return_value = mock_user
            
            event_id = uuid.uuid4()
            registration_times = []
            registration_count = 100
            
            for i in range(registration_count):
                registration_data = {
                    "display_name": fake.first_name(),
                    "category": fake.random_element(AttendeeCategory).value,
                    "age": fake.random_int(min=25, max=55),
                    "public_bio": fake.text(max_nb_chars=100),
                    "contact_email": fake.email(),
                    "contact_phone": fake.uk_phone_number(),
                    "contact_visible_to_matches": fake.boolean(),
                    "profile_visible": True
                }
                
                start_time = time.perf_counter()
                response = client.post(
                    f"/attendees/register/{event_id}",
                    json=registration_data
                )
                end_time = time.perf_counter()
                
                registration_time = (end_time - start_time) * 1000
                registration_times.append(registration_time)
                
                # Verify response
                assert response.status_code in [201, 400, 404, 422]
            
            # Performance analysis
            avg_time = statistics.mean(registration_times)
            median_time = statistics.median(registration_times)
            p95_time = sorted(registration_times)[int(0.95 * len(registration_times))]
            
            assert avg_time < 300, f"Average registration time too high: {avg_time:.2f}ms"
            assert median_time < 200, f"Median registration time too high: {median_time:.2f}ms"
            assert p95_time < 600, f"95th percentile too high: {p95_time:.2f}ms"
            
            print(f"Attendee registration performance:")
            print(f"  Average: {avg_time:.2f}ms")
            print(f"  Median: {median_time:.2f}ms")
            print(f"  95th percentile: {p95_time:.2f}ms")
    
    @pytest.mark.faker
    def test_api_endpoint_response_times(self, client, faker_instance):
        """Test response times for various API endpoints."""
        fake = setup_faker_providers(faker_instance)
        
        endpoints_to_test = [
            ("/", "GET", None),
            ("/health", "GET", None),
            ("/events/", "GET", {"limit": 10}),
        ]
        
        for endpoint, method, params in endpoints_to_test:
            response_times = []
            test_iterations = 20
            
            for _ in range(test_iterations):
                start_time = time.perf_counter()
                
                if method == "GET":
                    response = client.get(endpoint, params=params)
                else:
                    response = client.post(endpoint, json=params)
                
                end_time = time.perf_counter()
                
                response_time = (end_time - start_time) * 1000
                response_times.append(response_time)
                
                # Verify response is valid
                assert response.status_code < 500  # No server errors
            
            # Analyze endpoint performance
            avg_time = statistics.mean(response_times)
            p95_time = sorted(response_times)[int(0.95 * len(response_times))]
            
            print(f"{method} {endpoint} performance:")
            print(f"  Average: {avg_time:.2f}ms")
            print(f"  95th percentile: {p95_time:.2f}ms")
            
            # Performance thresholds based on endpoint complexity
            if endpoint in ["/", "/health"]:
                assert avg_time < 50, f"{endpoint} too slow: {avg_time:.2f}ms"
            else:
                assert avg_time < 200, f"{endpoint} too slow: {avg_time:.2f}ms"


@pytest.mark.performance
@pytest.mark.slow
class TestConcurrentLoadTesting:
    """Concurrent load testing with realistic user patterns."""
    
    @pytest.mark.faker
    def test_concurrent_event_operations(self, client, faker_instance):
        """Test concurrent event operations from multiple organizers."""
        fake = setup_faker_providers(faker_instance)
        
        def create_event_as_organizer(organizer_id):
            """Create an event as a specific organizer."""
            with patch("app.auth.current_active_organizer") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = organizer_id
                mock_user.is_organizer = True
                mock_user.full_name = fake.name()
                mock_auth.return_value = mock_user
                
                event_data = {
                    "name": fake.event_name(),
                    "description": fake.text(max_nb_chars=100),
                    "location": fake.venue_name(),
                    "event_date": fake.date_time_between(start_date="+1d", end_date="+14d").isoformat(),
                    "max_attendees": fake.random_int(min=20, max=80),
                    "min_attendees": fake.random_int(min=8, max=20)
                }
                
                start_time = time.perf_counter()
                response = client.post("/events/", json=event_data)
                end_time = time.perf_counter()
                
                return response.status_code, (end_time - start_time) * 1000
        
        # Create multiple concurrent organizers
        organizer_count = 10
        organizer_ids = [uuid.uuid4() for _ in range(organizer_count)]
        
        # Execute concurrent event creation
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(create_event_as_organizer, org_id) 
                for org_id in organizer_ids
            ]
            
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze concurrent performance
        successful_operations = [r for r in results if r[0] in [201, 400, 422]]
        response_times = [r[1] for r in successful_operations]
        
        if response_times:
            avg_concurrent_time = statistics.mean(response_times)
            max_concurrent_time = max(response_times)
            
            # Concurrent operations should not be significantly slower
            assert avg_concurrent_time < 1000, f"Concurrent operations too slow: {avg_concurrent_time:.2f}ms"
            assert max_concurrent_time < 3000, f"Worst concurrent time too slow: {max_concurrent_time:.2f}ms"
            
            print(f"Concurrent event creation ({organizer_count} organizers):")
            print(f"  Success rate: {len(successful_operations)}/{organizer_count}")
            print(f"  Average time: {avg_concurrent_time:.2f}ms")
            print(f"  Max time: {max_concurrent_time:.2f}ms")
    
    @pytest.mark.faker
    def test_concurrent_attendee_registrations(self, client, faker_instance):
        """Test concurrent attendee registrations for the same event."""
        fake = setup_faker_providers(faker_instance)
        
        event_id = uuid.uuid4()
        
        def register_attendee(attendee_number):
            """Register an attendee for the event."""
            with patch("app.auth.current_active_user") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_auth.return_value = mock_user
                
                registration_data = {
                    "display_name": f"{fake.first_name()} {attendee_number}",
                    "category": fake.random_element(AttendeeCategory).value,
                    "age": fake.random_int(min=25, max=55),
                    "contact_email": fake.email(),
                    "contact_phone": fake.uk_phone_number(),
                    "profile_visible": True
                }
                
                start_time = time.perf_counter()
                response = client.post(
                    f"/attendees/register/{event_id}",
                    json=registration_data
                )
                end_time = time.perf_counter()
                
                return response.status_code, (end_time - start_time) * 1000
        
        # Simulate simultaneous registration rush
        concurrent_registrations = 25
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(register_attendee, i)
                for i in range(concurrent_registrations)
            ]
            
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze concurrent registration performance
        handled_operations = [r for r in results if r[0] in [201, 400, 404, 409, 422]]
        response_times = [r[1] for r in handled_operations]
        
        if response_times:
            avg_time = statistics.mean(response_times)
            p95_time = sorted(response_times)[int(0.95 * len(response_times))]
            
            # Should handle concurrent registrations efficiently
            assert avg_time < 800, f"Concurrent registrations too slow: {avg_time:.2f}ms"
            assert p95_time < 2000, f"95th percentile too slow: {p95_time:.2f}ms"
            
            print(f"Concurrent registrations ({concurrent_registrations} attendees):")
            print(f"  Handled: {len(handled_operations)}/{concurrent_registrations}")
            print(f"  Average time: {avg_time:.2f}ms")
            print(f"  95th percentile: {p95_time:.2f}ms")
    
    @pytest.mark.faker
    def test_mixed_workload_simulation(self, client, faker_instance):
        """Test mixed workload simulation with realistic user patterns."""
        fake = setup_faker_providers(faker_instance)
        
        def organizer_workflow():
            """Simulate typical organizer workflow."""
            with patch("app.auth.current_active_organizer") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_user.is_organizer = True
                mock_user.full_name = fake.name()
                mock_auth.return_value = mock_user
                
                operations = []
                
                # Create event
                event_data = {
                    "name": fake.event_name(),
                    "event_date": fake.date_time_between(start_date="+1d", end_date="+14d").isoformat(),
                    "max_attendees": fake.random_int(min=30, max=100),
                    "min_attendees": fake.random_int(min=10, max=30)
                }
                
                start_time = time.perf_counter()
                response = client.post("/events/", json=event_data)
                operations.append(("create_event", time.perf_counter() - start_time, response.status_code))
                
                if response.status_code == 201:
                    event_id = response.json().get("id")
                    
                    # View event list
                    start_time = time.perf_counter()
                    response = client.get("/events/")
                    operations.append(("list_events", time.perf_counter() - start_time, response.status_code))
                    
                    # View event details
                    start_time = time.perf_counter()
                    response = client.get(f"/events/{event_id}")
                    operations.append(("view_event", time.perf_counter() - start_time, response.status_code))
                
                return operations
        
        def attendee_workflow():
            """Simulate typical attendee workflow."""
            with patch("app.auth.current_active_user") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_auth.return_value = mock_user
                
                operations = []
                event_id = uuid.uuid4()
                
                # Register for event
                registration_data = {
                    "display_name": fake.first_name(),
                    "category": fake.random_element(AttendeeCategory).value,
                    "contact_email": fake.email(),
                    "profile_visible": True
                }
                
                start_time = time.perf_counter()
                response = client.post(f"/attendees/register/{event_id}", json=registration_data)
                operations.append(("register", time.perf_counter() - start_time, response.status_code))
                
                # View matches (would normally require valid attendee)
                start_time = time.perf_counter()
                response = client.get("/attendees/my-matches")
                operations.append(("view_matches", time.perf_counter() - start_time, response.status_code))
                
                return operations
        
        # Execute mixed workload
        organizer_count = 5
        attendee_count = 15
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit organizer workflows
            organizer_futures = [
                executor.submit(organizer_workflow)
                for _ in range(organizer_count)
            ]
            
            # Submit attendee workflows
            attendee_futures = [
                executor.submit(attendee_workflow)
                for _ in range(attendee_count)
            ]
            
            # Collect results
            all_operations = []
            for future in as_completed(organizer_futures + attendee_futures):
                operations = future.result()
                all_operations.extend(operations)
        
        # Analyze mixed workload performance
        operation_stats = {}
        for operation_type, duration, status_code in all_operations:
            if operation_type not in operation_stats:
                operation_stats[operation_type] = {"times": [], "statuses": []}
            
            operation_stats[operation_type]["times"].append(duration * 1000)  # Convert to ms
            operation_stats[operation_type]["statuses"].append(status_code)
        
        # Performance analysis by operation type
        for operation_type, stats in operation_stats.items():
            times = stats["times"]
            if times:
                avg_time = statistics.mean(times)
                success_rate = len([s for s in stats["statuses"] if s < 400]) / len(stats["statuses"])
                
                print(f"{operation_type} performance:")
                print(f"  Average time: {avg_time:.2f}ms")
                print(f"  Success rate: {success_rate:.2%}")
                print(f"  Operations: {len(times)}")
                
                # Performance thresholds vary by operation
                if operation_type in ["list_events", "view_matches"]:
                    assert avg_time < 500, f"{operation_type} too slow: {avg_time:.2f}ms"
                else:
                    assert avg_time < 1000, f"{operation_type} too slow: {avg_time:.2f}ms"


@pytest.mark.performance
class TestDatabasePerformance:
    """Test database performance under load."""
    
    @given(
        query_limit=st.integers(min_value=10, max_value=100),
        search_complexity=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=10, deadline=8000)
    def test_database_query_performance(self, client, query_limit, search_complexity):
        """Test database query performance with varying parameters."""
        
        with patch("app.auth.current_active_organizer") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = uuid.uuid4()
            mock_user.is_organizer = True
            mock_auth.return_value = mock_user
            
            # Create complex search parameters
            search_params = {
                "limit": query_limit,
                "offset": 0,
            }
            
            # Add search complexity
            if search_complexity > 2:
                search_params["search"] = "test event"
            if search_complexity > 3:
                search_params["status_filter"] = EventStatus.DRAFT.value
            
            # Measure query time
            start_time = time.perf_counter()
            response = client.get("/events/", params=search_params)
            end_time = time.perf_counter()
            
            query_time = (end_time - start_time) * 1000
            
            # Verify response
            assert response.status_code in [200, 401, 403]
            
            # Performance should scale reasonably with parameters
            expected_max_time = 50 + (query_limit * 2) + (search_complexity * 50)
            assert query_time < expected_max_time, f"Query too slow for parameters: {query_time:.2f}ms"
    
    @pytest.mark.slow
    def test_database_connection_pooling(self, client):
        """Test database connection pooling under concurrent load."""
        
        def make_database_request(request_id):
            """Make a request that uses database connection."""
            with patch("app.auth.current_active_organizer") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_user.is_organizer = True
                mock_auth.return_value = mock_user
                
                start_time = time.perf_counter()
                response = client.get("/events/")
                end_time = time.perf_counter()
                
                return request_id, response.status_code, (end_time - start_time) * 1000
        
        # Simulate high database connection pressure
        concurrent_requests = 50
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(make_database_request, i)
                for i in range(concurrent_requests)
            ]
            
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze connection pooling performance
        response_times = [r[2] for r in results if r[1] in [200, 401, 403]]
        success_rate = len([r for r in results if r[1] < 400]) / len(results)
        
        if response_times:
            avg_time = statistics.mean(response_times)
            p95_time = sorted(response_times)[int(0.95 * len(response_times))]
            
            print(f"Database connection pooling ({concurrent_requests} concurrent):")
            print(f"  Success rate: {success_rate:.2%}")
            print(f"  Average time: {avg_time:.2f}ms")
            print(f"  95th percentile: {p95_time:.2f}ms")
            
            # Connection pooling should maintain reasonable performance
            assert success_rate >= 0.8, f"Too many connection failures: {success_rate:.2%}"
            assert avg_time < 1000, f"Average response too slow: {avg_time:.2f}ms"
            assert p95_time < 3000, f"95th percentile too slow: {p95_time:.2f}ms"


@pytest.mark.performance
class TestMemoryAndResourceUsage:
    """Test memory usage and resource consumption patterns."""
    
    @pytest.mark.faker
    def test_memory_usage_pattern(self, client, faker_instance):
        """Test memory usage patterns under typical workloads."""
        fake = setup_faker_providers(faker_instance)
        
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform memory-intensive operations
        operation_count = 100
        
        for i in range(operation_count):
            # Create large event data
            event_data = {
                "name": fake.event_name(),
                "description": fake.text(max_nb_chars=1000),
                "location": fake.venue_name(),
                "event_date": fake.date_time_between(start_date="+1d", end_date="+30d").isoformat(),
                "max_attendees": 200,
                "min_attendees": 50
            }
            
            with patch("app.auth.current_active_organizer") as mock_auth:
                mock_user = MagicMock()
                mock_user.id = uuid.uuid4()
                mock_user.is_organizer = True
                mock_auth.return_value = mock_user
                
                response = client.post("/events/", json=event_data)
                # Don't need to check response for memory test
        
        # Check final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"Memory usage test ({operation_count} operations):")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Memory increase: {memory_increase:.2f} MB")
        
        # Memory increase should be reasonable
        max_acceptable_increase = operation_count * 0.5  # 0.5 MB per operation max
        assert memory_increase < max_acceptable_increase, \
            f"Memory usage too high: {memory_increase:.2f} MB increase"
    
    def test_response_time_consistency(self, client):
        """Test that response times remain consistent over time."""
        
        # Warm up
        for _ in range(5):
            client.get("/health")
        
        # Measure response times over extended period
        response_times = []
        measurement_count = 50
        
        for i in range(measurement_count):
            start_time = time.perf_counter()
            response = client.get("/health")
            end_time = time.perf_counter()
            
            response_time = (end_time - start_time) * 1000
            response_times.append(response_time)
            
            assert response.status_code == 200
            
            # Small delay between requests
            time.sleep(0.01)
        
        # Analyze consistency
        avg_time = statistics.mean(response_times)
        std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
        min_time = min(response_times)
        max_time = max(response_times)
        
        print(f"Response time consistency ({measurement_count} requests):")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Std deviation: {std_dev:.2f}ms")
        print(f"  Min time: {min_time:.2f}ms")
        print(f"  Max time: {max_time:.2f}ms")
        
        # Response times should be consistent (low deviation)
        coefficient_of_variation = std_dev / avg_time if avg_time > 0 else 0
        assert coefficient_of_variation < 2.0, \
            f"Response times too inconsistent: CV = {coefficient_of_variation:.2f}"


# Utility functions for performance testing
def measure_operation_time(func, *args, **kwargs):
    """Measure the execution time of an operation."""
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    
    execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
    return result, execution_time


def analyze_response_times(times, operation_name="operation"):
    """Analyze and print response time statistics."""
    if not times:
        return
    
    avg_time = statistics.mean(times)
    median_time = statistics.median(times)
    std_dev = statistics.stdev(times) if len(times) > 1 else 0
    p95_time = sorted(times)[int(0.95 * len(times))] if len(times) >= 20 else max(times)
    
    print(f"{operation_name} performance statistics:")
    print(f"  Count: {len(times)}")
    print(f"  Average: {avg_time:.2f}ms")
    print(f"  Median: {median_time:.2f}ms")
    print(f"  Std Dev: {std_dev:.2f}ms")
    print(f"  95th percentile: {p95_time:.2f}ms")
    
    return {
        "count": len(times),
        "average": avg_time,
        "median": median_time,
        "std_dev": std_dev,
        "p95": p95_time
    }


# Performance test configuration
pytestmark = [
    pytest.mark.performance,
    pytest.mark.slow,  # Performance tests can be slow
]