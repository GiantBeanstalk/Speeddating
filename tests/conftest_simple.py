"""
Simplified test configuration without full app dependencies.
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from faker import Faker
from hypothesis import settings as hypothesis_settings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

# Set test environment
os.environ["SPEEDDATING_ENV"] = "testing"

# Configure Hypothesis for testing
hypothesis_settings.register_profile(
    "test", 
    max_examples=10,
    deadline=2000,
    suppress_health_check=["too_slow"]
)
hypothesis_settings.load_profile("test")

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def faker_instance() -> Faker:
    """Create a Faker instance with UK locale for realistic test data."""
    fake = Faker("en_GB")
    fake.seed_instance(12345)
    return fake