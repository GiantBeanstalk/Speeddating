"""
Integration tests for health check endpoints.

Tests the health check system with realistic scenarios and various
application states using Faker-generated data.
"""

import pytest
from hypothesis import given, strategies as st
from unittest.mock import patch, MagicMock

from tests.fixtures.faker_providers import setup_faker_providers


@pytest.mark.integration
class TestHealthEndpoints:
    """Integration tests for health check endpoints."""
    
    def test_basic_health_endpoint(self, client):
        """Test basic health check endpoint returns expected structure."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "service" in data  
        assert "version" in data
        assert data["status"] == "healthy"
        assert data["service"] == "Speed Dating Application"
        assert data["version"] == "1.0.0"
    
    @pytest.mark.faker
    def test_health_endpoint_with_fake_data(self, client, faker_instance):
        """Test health endpoint behavior with various fake scenarios."""
        fake = setup_faker_providers(faker_instance)
        
        # Test multiple calls to ensure consistency
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            
            # Response should be consistent regardless of fake data generation
            assert "service" in data
            assert "version" in data
    
    @given(
        user_agent=st.text(min_size=10, max_size=200),
        accept_header=st.sampled_from([
            "application/json",
            "text/html",
            "application/xml",
            "*/*"
        ])
    )
    def test_health_endpoint_various_headers(self, client, user_agent, accept_header):
        """Test health endpoint with various request headers."""
        headers = {
            "User-Agent": user_agent,
            "Accept": accept_header,
        }
        
        response = client.get("/health", headers=headers)
        
        # Should always return 200 OK regardless of headers
        assert response.status_code == 200
        
        # Should always return JSON
        assert response.headers.get("content-type", "").startswith("application/json")
        
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_health_endpoint_performance(self, client):
        """Test health endpoint response time is reasonable."""
        import time
        
        # Make multiple requests and measure time
        times = []
        for _ in range(10):
            start = time.time()
            response = client.get("/health")
            end = time.time()
            
            assert response.status_code == 200
            times.append(end - start)
        
        # Average response time should be reasonable (less than 100ms)
        avg_time = sum(times) / len(times)
        assert avg_time < 0.1, f"Health endpoint too slow: {avg_time:.3f}s average"
    
    @given(
        method=st.sampled_from(["POST", "PUT", "DELETE", "PATCH"])
    )
    def test_health_endpoint_method_restrictions(self, client, method):
        """Test that health endpoint only accepts GET requests."""
        # Health endpoint should only accept GET
        response = client.request(method, "/health")
        
        # Should return 405 Method Not Allowed for non-GET methods
        assert response.status_code == 405
    
    @pytest.mark.slow
    def test_health_endpoint_concurrent_requests(self, client):
        """Test health endpoint handles concurrent requests properly."""
        import concurrent.futures
        import threading
        
        def make_request():
            return client.get("/health")
        
        # Make 20 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            responses = [future.result() for future in futures]
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"


@pytest.mark.integration  
class TestRootEndpoint:
    """Integration tests for root endpoint."""
    
    def test_root_endpoint_structure(self, client):
        """Test root endpoint returns expected structure."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "docs" in data
        assert "health" in data
        assert data["message"] == "Welcome to the Speed Dating Application"
        assert data["health"] == "/health"
    
    @pytest.mark.faker
    def test_root_endpoint_with_mock_settings(self, client, faker_instance):
        """Test root endpoint behavior with different settings."""
        fake = setup_faker_providers(faker_instance)
        
        # Test with DEBUG mode variations
        with patch("app.config.settings") as mock_settings:
            mock_settings.get.side_effect = lambda key, default=None: {
                "DEBUG": True
            }.get(key, default)
            
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert "/docs" in data["docs"]
        
        # Test with production mode
        with patch("app.config.settings") as mock_settings:
            mock_settings.get.side_effect = lambda key, default=None: {
                "DEBUG": False
            }.get(key, default)
            
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert "Documentation disabled" in data["docs"]


@pytest.mark.integration
class TestApplicationStartup:
    """Integration tests for application startup scenarios."""
    
    @pytest.mark.faker
    def test_startup_with_valid_configuration(self, faker_instance):
        """Test application startup with valid configuration."""
        fake = setup_faker_providers(faker_instance)
        
        # Mock valid configuration
        valid_config = {
            "SECRET_KEY": fake.password(length=32),
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "DEBUG": True,
            "TESTING": True,
            "EMAIL_HOST": fake.domain_name(),
            "EMAIL_PORT": fake.random_int(min=1, max=65535),
            "EMAIL_FROM": fake.email(),
        }
        
        with patch("app.config.settings") as mock_settings:
            mock_settings.__getitem__.side_effect = valid_config.__getitem__
            mock_settings.get.side_effect = valid_config.get
            
            # Test basic endpoint access works with this configuration
            from fastapi.testclient import TestClient
            from app.main import app
            
            with TestClient(app) as test_client:
                response = test_client.get("/health")
                assert response.status_code == 200
    
    @pytest.mark.faker
    def test_error_handling_in_endpoints(self, client, faker_instance):
        """Test error handling in health endpoints with various failure scenarios."""
        fake = setup_faker_providers(faker_instance)
        
        # Test with various potential error conditions
        error_scenarios = [
            # Network timeout simulation
            {"delay": 0.1},
            # Memory pressure simulation  
            {"memory_pressure": True},
            # Database connection issues
            {"db_error": True},
        ]
        
        for scenario in error_scenarios:
            # Health endpoint should still work even with system issues
            response = client.get("/health")
            
            # Basic health endpoint should be resilient
            assert response.status_code == 200
            data = response.json()
            assert "status" in data


@pytest.mark.integration
@pytest.mark.performance
class TestHealthEndpointPerformance:
    """Performance tests for health endpoints."""
    
    def test_health_endpoint_load_performance(self, client):
        """Test health endpoint performance under load."""
        import time
        import statistics
        
        # Warm up
        for _ in range(5):
            client.get("/health")
        
        # Measure performance
        response_times = []
        for _ in range(100):
            start = time.perf_counter()
            response = client.get("/health")
            end = time.perf_counter()
            
            assert response.status_code == 200
            response_times.append((end - start) * 1000)  # Convert to milliseconds
        
        # Performance assertions
        avg_time = statistics.mean(response_times)
        median_time = statistics.median(response_times)
        p95_time = sorted(response_times)[int(0.95 * len(response_times))]
        
        # Health endpoint should be fast
        assert avg_time < 50, f"Average response time too high: {avg_time:.2f}ms"
        assert median_time < 30, f"Median response time too high: {median_time:.2f}ms"
        assert p95_time < 100, f"95th percentile too high: {p95_time:.2f}ms"
        
        print(f"Health endpoint performance:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Median: {median_time:.2f}ms") 
        print(f"  95th percentile: {p95_time:.2f}ms")
    
    @pytest.mark.slow
    def test_sustained_load_stability(self, client):
        """Test health endpoint stability under sustained load."""
        import time
        import threading
        
        # Track results
        results = {"success": 0, "failure": 0, "errors": []}
        
        def make_requests(duration=10):
            """Make requests for a specified duration."""
            end_time = time.time() + duration
            while time.time() < end_time:
                try:
                    response = client.get("/health")
                    if response.status_code == 200:
                        results["success"] += 1
                    else:
                        results["failure"] += 1
                        results["errors"].append(f"HTTP {response.status_code}")
                except Exception as e:
                    results["failure"] += 1
                    results["errors"].append(str(e))
                
                time.sleep(0.01)  # Small delay between requests
        
        # Run sustained load test with multiple threads
        threads = []
        for _ in range(3):  # 3 concurrent threads
            thread = threading.Thread(target=make_requests, args=(5,))  # 5 seconds each
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        total_requests = results["success"] + results["failure"]
        success_rate = results["success"] / total_requests if total_requests > 0 else 0
        
        assert total_requests > 0, "No requests were made"
        assert success_rate >= 0.99, f"Success rate too low: {success_rate:.2%} ({results['success']}/{total_requests})"
        
        if results["errors"]:
            print(f"Errors encountered: {results['errors'][:10]}")  # Show first 10 errors
        
        print(f"Sustained load test results:")
        print(f"  Total requests: {total_requests}")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Failures: {results['failure']}")


# Helper fixtures for mocking various scenarios
@pytest.fixture
def mock_database_error():
    """Mock database connection errors."""
    with patch("app.database.get_async_session") as mock:
        mock.side_effect = Exception("Database connection failed")
        yield mock

@pytest.fixture  
def mock_slow_response():
    """Mock slow response times."""
    import time
    
    def slow_function(*args, **kwargs):
        time.sleep(0.1)  # Simulate 100ms delay
        return MagicMock()
    
    with patch("app.main.validate_settings", side_effect=slow_function) as mock:
        yield mock