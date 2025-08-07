"""
Test configuration and shared fixtures for the Speed Dating application.

Provides common fixtures for database sessions, test clients, authentication,
and test data generation using Hypothesis strategies and Faker providers.
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import patch

import pytest
import pytest_asyncio
from faker import Faker
from fastapi.testclient import TestClient
from hypothesis import settings as hypothesis_settings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_async_session
from app.main import app
from app.models import User

# Set test environment
os.environ["SPEEDDATING_ENV"] = "testing"

# Configure Hypothesis for testing
hypothesis_settings.register_profile(
    "test", 
    max_examples=10,
    deadline=2000,
    suppress_health_check=["too_slow"]
)
hypothesis_settings.register_profile(
    "ci", 
    max_examples=50,
    deadline=5000,
    suppress_health_check=["too_slow", "data_too_large"]
)
hypothesis_settings.load_profile(
    os.environ.get("HYPOTHESIS_PROFILE", "test")
)

# Test database URL - use in-memory SQLite for fast tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()


@pytest.fixture
def client(db_session: AsyncSession) -> Generator[TestClient, None, None]:
    """Create a test client with overridden database session."""
    
    def override_get_db():
        return db_session
    
    app.dependency_overrides[get_async_session] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def faker_instance() -> Faker:
    """Create a Faker instance with UK locale for realistic test data."""
    fake = Faker("en_GB")  # UK locale for phone numbers, addresses, etc.
    fake.seed_instance(12345)  # Reproducible fake data
    return fake


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    test_settings = {
        "SECRET_KEY": "test_secret_key_at_least_32_characters_long",
        "DATABASE_URL": TEST_DATABASE_URL,
        "DEBUG": True,
        "TESTING": True,
        "EMAIL_HOST": "localhost",
        "EMAIL_PORT": 587,
        "EMAIL_USE_TLS": False,
        "EMAIL_FROM": "test@speeddating.test",
        "ALLOWED_ORIGINS": ["http://testserver", "http://localhost:3000"],
        "JWT_ALGORITHM": "HS256",
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": 30,
        "JWT_REFRESH_TOKEN_EXPIRE_DAYS": 30,
        "SUPER_USER_SECRET": "test_super_secret_at_least_32_chars",
    }
    
    with patch.object(settings, "__getitem__", side_effect=test_settings.__getitem__):
        with patch.object(settings, "get", side_effect=test_settings.get):
            yield test_settings


@pytest.fixture
def sample_user_data(faker_instance: Faker) -> dict:
    """Generate sample user data using Faker."""
    return {
        "email": faker_instance.email(),
        "first_name": faker_instance.first_name(),
        "last_name": faker_instance.last_name(),
        "password": faker_instance.password(length=12),
        "is_active": True,
        "is_verified": True,
        "is_superuser": False,
    }


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, sample_user_data: dict) -> User:
    """Create a test user in the database."""
    from app.auth import get_user_manager
    
    # Remove password from data as it needs to be hashed
    password = sample_user_data.pop("password")
    
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def test_superuser(db_session: AsyncSession, faker_instance: Faker) -> User:
    """Create a test superuser in the database."""
    user_data = {
        "email": faker_instance.email(),
        "first_name": faker_instance.first_name(),
        "last_name": faker_instance.last_name(),
        "is_active": True,
        "is_verified": True,
        "is_superuser": True,
    }
    
    user = User(**user_data)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest.fixture
def authenticated_client(client: TestClient, test_user: User) -> TestClient:
    """Create an authenticated test client."""
    # Mock authentication - in real implementation you'd generate a proper JWT
    with patch("app.auth.current_user", return_value=test_user):
        yield client


@pytest.fixture
def superuser_client(client: TestClient, test_superuser: User) -> TestClient:
    """Create a superuser authenticated test client."""
    with patch("app.auth.current_superuser", return_value=test_superuser):
        yield client


# Test markers for better organization
pytest.register_assert_rewrite("tests.helpers")

# Collection of useful test utilities
class TestUtils:
    """Utility functions for testing."""
    
    @staticmethod
    def assert_response_success(response, expected_status=200):
        """Assert that a response is successful."""
        assert response.status_code == expected_status
        return response.json() if response.headers.get("content-type", "").startswith("application/json") else response.content
    
    @staticmethod
    def assert_response_error(response, expected_status=400):
        """Assert that a response contains an error."""
        assert response.status_code >= expected_status
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "detail" in data or "error" in data
    
    @staticmethod
    async def create_test_data(session: AsyncSession, model_class, **kwargs):
        """Helper to create test data."""
        instance = model_class(**kwargs)
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance


@pytest.fixture
def test_utils() -> TestUtils:
    """Provide test utility functions."""
    return TestUtils()