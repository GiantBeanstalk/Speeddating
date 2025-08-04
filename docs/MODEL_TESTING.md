# Data Models Testing Guide

## Overview

This guide provides comprehensive testing strategies and examples for validating the Speed Dating Application's data models, ensuring data integrity, relationship consistency, and business logic correctness.

## Testing Setup

### Test Configuration

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
from app.database import Base
from app.models import *

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest_asyncio.fixture
async def test_session(test_engine):
    """Create test database session."""
    async with AsyncSession(test_engine) as session:
        yield session
```

### Test Utilities

```python
# tests/utils.py
import uuid
from datetime import datetime, timedelta
from app.models import *

class ModelFactory:
    """Factory for creating test model instances."""
    
    @staticmethod
    def create_user(**kwargs):
        defaults = {
            "email": f"test{uuid.uuid4().hex[:8]}@example.com",
            "is_active": True,
            "is_verified": True,
            "first_name": "Test",
            "last_name": "User"
        }
        defaults.update(kwargs)
        return User(**defaults)
    
    @staticmethod
    def create_event(organizer_id: uuid.UUID, **kwargs):
        defaults = {
            "name": f"Test Event {uuid.uuid4().hex[:8]}",
            "event_date": datetime.utcnow() + timedelta(days=7),
            "organizer_id": organizer_id,
            "max_attendees": 20,
            "round_duration_minutes": 5
        }
        defaults.update(kwargs)
        return Event(**defaults)
    
    @staticmethod
    def create_attendee(user_id: uuid.UUID, event_id: uuid.UUID, **kwargs):
        defaults = {
            "user_id": user_id,
            "event_id": event_id,
            "display_name": f"Attendee {uuid.uuid4().hex[:8]}",
            "category": AttendeeCategory.TOP_MALE
        }
        defaults.update(kwargs)
        return Attendee(**defaults)
```

## Model-Specific Tests

### User Model Tests

```python
# tests/test_models/test_user.py
import pytest
from app.models import User, OAuthAccount

@pytest.mark.asyncio
async def test_user_creation(test_session):
    """Test basic user creation."""
    user = User(
        email="test@example.com",
        first_name="John",
        last_name="Doe"
    )
    
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.full_name == "John Doe"
    assert user.is_active is True
    assert user.created_at is not None

@pytest.mark.asyncio
async def test_user_full_name_property(test_session):
    """Test full_name property variations."""
    # Test with first and last name
    user1 = User(email="test1@example.com", first_name="John", last_name="Doe")
    assert user1.full_name == "John Doe"
    
    # Test with display name only
    user2 = User(email="test2@example.com", display_name="Johnny")
    assert user2.full_name == "Johnny"
    
    # Test with email fallback
    user3 = User(email="test3@example.com")
    assert user3.full_name == "test3"

@pytest.mark.asyncio
async def test_user_oauth_accounts(test_session):
    """Test OAuth account relationships."""
    user = User(email="test@example.com")
    test_session.add(user)
    await test_session.commit()
    
    # Add OAuth accounts
    google_account = OAuthAccount(
        user_id=user.id,
        oauth_name="google",
        account_id="123456789",
        access_token="token_123"
    )
    facebook_account = OAuthAccount(
        user_id=user.id,
        oauth_name="facebook",
        account_id="987654321",
        access_token="token_456"
    )
    
    test_session.add_all([google_account, facebook_account])
    await test_session.commit()
    
    # Refresh and check relationships
    await test_session.refresh(user)
    assert len(user.oauth_accounts) == 2
    
    provider_names = {acc.oauth_name for acc in user.oauth_accounts}
    assert provider_names == {"google", "facebook"}

@pytest.mark.asyncio
async def test_user_email_uniqueness(test_session):
    """Test email uniqueness constraint."""
    user1 = User(email="duplicate@example.com")
    user2 = User(email="duplicate@example.com")
    
    test_session.add(user1)
    await test_session.commit()
    
    test_session.add(user2)
    with pytest.raises(Exception):  # IntegrityError
        await test_session.commit()
```

### Event Model Tests

```python
# tests/test_models/test_event.py
import pytest
from datetime import datetime, timedelta
from app.models import Event, EventStatus, User

@pytest.mark.asyncio
async def test_event_creation(test_session):
    """Test event creation with organizer."""
    organizer = User(email="organizer@example.com", is_organizer=True)
    test_session.add(organizer)
    await test_session.commit()
    
    event = Event(
        name="Test Speed Dating",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id,
        location="Test Venue"
    )
    
    test_session.add(event)
    await test_session.commit()
    await test_session.refresh(event)
    
    assert event.id is not None
    assert event.name == "Test Speed Dating"
    assert event.status == EventStatus.DRAFT
    assert event.organizer_id == organizer.id

@pytest.mark.asyncio
async def test_event_properties(test_session):
    """Test event computed properties."""
    organizer = User(email="organizer@example.com")
    test_session.add(organizer)
    await test_session.commit()
    
    event = Event(
        name="Test Event",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id,
        max_attendees=20,
        min_attendees=6,
        registration_deadline=datetime.utcnow() + timedelta(days=3)
    )
    
    test_session.add(event)
    await test_session.commit()
    
    # Test properties
    assert event.is_active is False
    assert event.is_registration_open is True
    assert event.attendee_count == 0
    assert event.is_full is False
    assert event.has_minimum_attendees is False

@pytest.mark.asyncio
async def test_event_qr_secret_generation(test_session):
    """Test QR secret key generation."""
    organizer = User(email="organizer@example.com")
    test_session.add(organizer)
    await test_session.commit()
    
    event = Event(
        name="QR Test Event",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id
    )
    
    # Initially no QR secret
    assert event.qr_secret_key is None
    
    # Generate QR secret
    secret = event.generate_qr_secret()
    assert secret is not None
    assert len(secret) > 20
    assert event.qr_secret_key == secret

@pytest.mark.asyncio
async def test_event_duration_calculation(test_session):
    """Test event duration calculation."""
    organizer = User(email="organizer@example.com")
    test_session.add(organizer)
    await test_session.commit()
    
    event = Event(
        name="Duration Test",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id,
        round_duration_minutes=5,
        break_duration_minutes=2,
        total_rounds=10
    )
    
    duration = event.get_event_duration()
    
    # 10 rounds * 5 minutes + 9 breaks * 2 minutes + 30 minutes setup
    expected_minutes = (10 * 5) + (9 * 2) + 30  # 98 minutes
    assert duration.total_seconds() == expected_minutes * 60
```

### Attendee Model Tests

```python
# tests/test_models/test_attendee.py
import pytest
from app.models import Attendee, AttendeeCategory, User, Event

@pytest.mark.asyncio
async def test_attendee_creation(test_session):
    """Test attendee creation and relationships."""
    # Create user and event
    user = User(email="attendee@example.com")
    organizer = User(email="organizer@example.com")
    test_session.add_all([user, organizer])
    await test_session.commit()
    
    event = Event(
        name="Test Event",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id
    )
    test_session.add(event)
    await test_session.commit()
    
    # Create attendee
    attendee = Attendee(
        user_id=user.id,
        event_id=event.id,
        display_name="Test Attendee",
        category=AttendeeCategory.TOP_MALE,
        age=25
    )
    
    test_session.add(attendee)
    await test_session.commit()
    await test_session.refresh(attendee)
    
    assert attendee.id is not None
    assert attendee.category == AttendeeCategory.TOP_MALE
    assert attendee.checked_in is False

@pytest.mark.asyncio
async def test_attendee_qr_token_generation(test_session):
    """Test QR token generation for attendees."""
    user = User(email="test@example.com")
    organizer = User(email="organizer@example.com")
    test_session.add_all([user, organizer])
    await test_session.commit()
    
    event = Event(
        name="QR Event",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id
    )
    test_session.add(event)
    await test_session.commit()
    
    attendee = Attendee(
        user_id=user.id,
        event_id=event.id,
        display_name="QR Test",
        category=AttendeeCategory.TOP_FEMALE
    )
    
    # Generate QR token
    token = attendee.generate_qr_token()
    
    assert token is not None
    assert len(token) > 20
    assert attendee.qr_token == token
    assert attendee.qr_generated_at is not None

@pytest.mark.asyncio
async def test_attendee_matching_logic(test_session):
    """Test attendee matching compatibility."""
    user1 = User(email="user1@example.com")
    user2 = User(email="user2@example.com")
    organizer = User(email="organizer@example.com")
    test_session.add_all([user1, user2, organizer])
    await test_session.commit()
    
    event = Event(
        name="Match Test",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id
    )
    test_session.add(event)
    await test_session.commit()
    
    # Create attendees with different categories
    attendee1 = Attendee(
        user_id=user1.id,
        event_id=event.id,
        display_name="Top Male",
        category=AttendeeCategory.TOP_MALE
    )
    attendee2 = Attendee(
        user_id=user2.id,
        event_id=event.id,
        display_name="Top Female",
        category=AttendeeCategory.TOP_FEMALE
    )
    
    test_session.add_all([attendee1, attendee2])
    await test_session.commit()
    
    # Test matching logic
    assert attendee1.is_interested_in_category(AttendeeCategory.TOP_FEMALE) is True
    assert attendee1.is_interested_in_category(AttendeeCategory.TOP_MALE) is False
    assert attendee1.can_match_with(attendee2) is True

@pytest.mark.asyncio
async def test_attendee_uniqueness_constraint(test_session):
    """Test that users can't register twice for same event."""
    user = User(email="test@example.com")
    organizer = User(email="organizer@example.com")
    test_session.add_all([user, organizer])
    await test_session.commit()
    
    event = Event(
        name="Unique Test",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id
    )
    test_session.add(event)
    await test_session.commit()
    
    # First registration
    attendee1 = Attendee(
        user_id=user.id,
        event_id=event.id,
        display_name="First Registration",
        category=AttendeeCategory.TOP_MALE
    )
    test_session.add(attendee1)
    await test_session.commit()
    
    # Second registration (should fail)
    attendee2 = Attendee(
        user_id=user.id,
        event_id=event.id,
        display_name="Second Registration",
        category=AttendeeCategory.TOP_FEMALE
    )
    test_session.add(attendee2)
    
    with pytest.raises(Exception):  # IntegrityError
        await test_session.commit()
```

### Match Model Tests

```python
# tests/test_models/test_match.py
import pytest
from app.models import Match, MatchResponse, Attendee, Round, Event, User

@pytest.mark.asyncio
async def test_match_creation_and_responses(test_session):
    """Test match creation and response handling."""
    # Setup users, event, and attendees
    user1 = User(email="user1@example.com")
    user2 = User(email="user2@example.com")
    organizer = User(email="organizer@example.com")
    test_session.add_all([user1, user2, organizer])
    await test_session.commit()
    
    event = Event(
        name="Match Test",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id
    )
    test_session.add(event)
    await test_session.commit()
    
    round_obj = Round(
        event_id=event.id,
        round_number=1,
        duration_minutes=5
    )
    test_session.add(round_obj)
    await test_session.commit()
    
    attendee1 = Attendee(
        user_id=user1.id,
        event_id=event.id,
        display_name="Attendee 1",
        category=AttendeeCategory.TOP_MALE
    )
    attendee2 = Attendee(
        user_id=user2.id,
        event_id=event.id,
        display_name="Attendee 2",
        category=AttendeeCategory.TOP_FEMALE
    )
    test_session.add_all([attendee1, attendee2])
    await test_session.commit()
    
    # Create match
    match = Match(
        event_id=event.id,
        round_id=round_obj.id,
        attendee1_id=attendee1.id,
        attendee2_id=attendee2.id,
        table_number=1
    )
    
    test_session.add(match)
    await test_session.commit()
    await test_session.refresh(match)
    
    # Test initial state
    assert match.attendee1_response == MatchResponse.NO_RESPONSE
    assert match.attendee2_response == MatchResponse.NO_RESPONSE
    assert match.is_completed is False
    assert match.both_responded is False

@pytest.mark.asyncio
async def test_match_response_handling(test_session):
    """Test setting and getting match responses."""
    # Setup (abbreviated for brevity)
    user1 = User(email="user1@example.com")
    user2 = User(email="user2@example.com")
    organizer = User(email="organizer@example.com")
    test_session.add_all([user1, user2, organizer])
    await test_session.commit()
    
    event = Event(
        name="Response Test",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id
    )
    test_session.add(event)
    await test_session.commit()
    
    round_obj = Round(event_id=event.id, round_number=1)
    test_session.add(round_obj)
    await test_session.commit()
    
    attendee1 = Attendee(
        user_id=user1.id, event_id=event.id,
        display_name="A1", category=AttendeeCategory.TOP_MALE
    )
    attendee2 = Attendee(
        user_id=user2.id, event_id=event.id,
        display_name="A2", category=AttendeeCategory.TOP_FEMALE
    )
    test_session.add_all([attendee1, attendee2])
    await test_session.commit()
    
    match = Match(
        event_id=event.id,
        round_id=round_obj.id,
        attendee1_id=attendee1.id,
        attendee2_id=attendee2.id,
        table_number=1
    )
    test_session.add(match)
    await test_session.commit()
    
    # Set responses
    success1 = match.set_attendee_response(
        attendee1.id, MatchResponse.YES, "Great conversation!"
    )
    success2 = match.set_attendee_response(
        attendee2.id, MatchResponse.YES, "Really enjoyed it!"
    )
    
    assert success1 is True
    assert success2 is True
    assert match.is_completed is True
    assert match.is_mutual_match is True
    assert match.has_mutual_interest is True
    assert match.attendee1_notes == "Great conversation!"
    assert match.attendee2_notes == "Really enjoyed it!"

@pytest.mark.asyncio
async def test_match_mutual_interest_scenarios(test_session):
    """Test various mutual interest scenarios."""
    # Test data setup (abbreviated)
    match = Match()  # Assuming properly set up match
    
    # Test YES/YES
    match.attendee1_response = MatchResponse.YES
    match.attendee2_response = MatchResponse.YES
    assert match.is_mutual_match is True
    assert match.has_mutual_interest is True
    
    # Test MAYBE/MAYBE
    match.attendee1_response = MatchResponse.MAYBE
    match.attendee2_response = MatchResponse.MAYBE
    assert match.is_mutual_maybe is True
    assert match.has_mutual_interest is True
    
    # Test YES/MAYBE
    match.attendee1_response = MatchResponse.YES
    match.attendee2_response = MatchResponse.MAYBE
    assert match.is_mutual_match is False
    assert match.has_mutual_interest is True
    
    # Test NO/YES
    match.attendee1_response = MatchResponse.NO
    match.attendee2_response = MatchResponse.YES
    assert match.has_mutual_interest is False
```

### QRLogin Model Tests

```python
# tests/test_models/test_qr_login.py
import pytest
from datetime import datetime, timedelta
from app.models import QRLogin, User, Event, Attendee

@pytest.mark.asyncio
async def test_qr_login_token_generation(test_session):
    """Test QR login token generation and validation."""
    user = User(email="test@example.com")
    organizer = User(email="organizer@example.com")
    test_session.add_all([user, organizer])
    await test_session.commit()
    
    event = Event(
        name="QR Test",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id
    )
    test_session.add(event)
    await test_session.commit()
    
    attendee = Attendee(
        user_id=user.id,
        event_id=event.id,
        display_name="QR Attendee",
        category=AttendeeCategory.TOP_MALE
    )
    test_session.add(attendee)
    await test_session.commit()
    
    # Create QR login token
    qr_login = QRLogin.create_for_attendee(
        attendee_id=attendee.id,
        event_id=event.id,
        user_id=user.id,
        expire_hours=24
    )
    
    test_session.add(qr_login)
    await test_session.commit()
    await test_session.refresh(qr_login)
    
    assert qr_login.token is not None
    assert qr_login.token_hash is not None
    assert qr_login.is_valid is True
    assert qr_login.is_expired is False

@pytest.mark.asyncio
async def test_qr_login_token_usage(test_session):
    """Test QR token usage and limits."""
    # Setup (abbreviated)
    qr_login = QRLogin(
        event_id=uuid.uuid4(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
        max_uses=3
    )
    qr_login.generate_token()
    qr_login.hash_token()
    
    # Test usage
    assert qr_login.usage_count == 0
    assert qr_login.has_remaining_uses is True
    
    # Use token multiple times
    for i in range(3):
        success = qr_login.use_token(ip_address="127.0.0.1")
        assert success is True
        assert qr_login.usage_count == i + 1
    
    # Fourth use should fail
    success = qr_login.use_token()
    assert success is False
    assert qr_login.is_active is False

@pytest.mark.asyncio
async def test_qr_login_token_expiration(test_session):
    """Test QR token expiration handling."""
    # Create expired token
    qr_login = QRLogin(
        event_id=uuid.uuid4(),
        expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired
    )
    qr_login.generate_token()
    qr_login.hash_token()
    
    assert qr_login.is_expired is True
    assert qr_login.is_valid is False
    
    # Try to use expired token
    success = qr_login.use_token()
    assert success is False

@pytest.mark.asyncio
async def test_qr_login_token_revocation(test_session):
    """Test QR token revocation."""
    qr_login = QRLogin(
        event_id=uuid.uuid4(),
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    qr_login.generate_token()
    qr_login.hash_token()
    
    assert qr_login.is_valid is True
    
    # Revoke token
    qr_login.revoke_token("Security concern")
    
    assert qr_login.is_revoked is True
    assert qr_login.is_valid is False
    assert qr_login.revoked_reason == "Security concern"
    assert qr_login.revoked_at is not None
```

## Integration Tests

### Cross-Model Relationship Tests

```python
# tests/test_integration/test_relationships.py
import pytest
from app.models import *

@pytest.mark.asyncio
async def test_complete_event_workflow(test_session):
    """Test complete event workflow with all models."""
    # Create organizer
    organizer = User(
        email="organizer@example.com",
        is_organizer=True,
        first_name="Event",
        last_name="Organizer"
    )
    test_session.add(organizer)
    await test_session.commit()
    
    # Create event
    event = Event(
        name="Integration Test Event",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id,
        max_attendees=10,
        round_duration_minutes=5
    )
    test_session.add(event)
    await test_session.commit()
    
    # Create attendees
    attendees = []
    for i in range(4):
        user = User(email=f"attendee{i}@example.com")
        test_session.add(user)
        await test_session.commit()
        
        attendee = Attendee(
            user_id=user.id,
            event_id=event.id,
            display_name=f"Attendee {i}",
            category=AttendeeCategory.TOP_MALE if i % 2 == 0 else AttendeeCategory.TOP_FEMALE
        )
        attendees.append(attendee)
        test_session.add(attendee)
    
    await test_session.commit()
    
    # Create rounds and matches
    round1 = Round(
        event_id=event.id,
        round_number=1,
        duration_minutes=5
    )
    test_session.add(round1)
    await test_session.commit()
    
    # Create matches
    match1 = Match(
        event_id=event.id,
        round_id=round1.id,
        attendee1_id=attendees[0].id,
        attendee2_id=attendees[1].id,
        table_number=1
    )
    match2 = Match(
        event_id=event.id,
        round_id=round1.id,
        attendee1_id=attendees[2].id,
        attendee2_id=attendees[3].id,
        table_number=2
    )
    test_session.add_all([match1, match2])
    await test_session.commit()
    
    # Verify relationships
    await test_session.refresh(event)
    assert len(event.attendees) == 4
    assert len(event.rounds) == 1
    assert len(event.matches) == 2
    
    await test_session.refresh(round1)
    assert len(round1.matches) == 2

@pytest.mark.asyncio
async def test_cascade_deletion(test_session):
    """Test cascade deletion behavior."""
    # Create complete structure
    organizer = User(email="organizer@example.com")
    test_session.add(organizer)
    await test_session.commit()
    
    event = Event(
        name="Cascade Test",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id
    )
    test_session.add(event)
    await test_session.commit()
    
    user = User(email="attendee@example.com")
    test_session.add(user)
    await test_session.commit()
    
    attendee = Attendee(
        user_id=user.id,
        event_id=event.id,
        display_name="Test Attendee",
        category=AttendeeCategory.TOP_MALE
    )
    test_session.add(attendee)
    await test_session.commit()
    
    # Delete event (should cascade to attendee)
    await test_session.delete(event)
    await test_session.commit()
    
    # Verify attendee was deleted
    remaining_attendee = await test_session.get(Attendee, attendee.id)
    assert remaining_attendee is None
```

## Performance Tests

### Query Performance Tests

```python
# tests/test_performance/test_queries.py
import pytest
import time
from sqlalchemy import select

@pytest.mark.asyncio
async def test_bulk_attendee_creation_performance(test_session):
    """Test bulk attendee creation performance."""
    organizer = User(email="organizer@example.com")
    test_session.add(organizer)
    await test_session.commit()
    
    event = Event(
        name="Performance Test",
        event_date=datetime.utcnow() + timedelta(days=7),
        organizer_id=organizer.id
    )
    test_session.add(event)
    await test_session.commit()
    
    # Create many users and attendees
    start_time = time.time()
    
    users = []
    attendees = []
    for i in range(100):
        user = User(email=f"perf_test_{i}@example.com")
        users.append(user)
        
        attendee = Attendee(
            user_id=user.id,
            event_id=event.id,
            display_name=f"Attendee {i}",
            category=AttendeeCategory.TOP_MALE if i % 2 == 0 else AttendeeCategory.TOP_FEMALE
        )
        attendees.append(attendee)
    
    test_session.add_all(users)
    await test_session.commit()
    
    # Now add attendees with proper user IDs
    for attendee in attendees:
        # Find the corresponding user
        attendee.user_id = next(u.id for u in users if u.email == f"perf_test_{attendees.index(attendee)}@example.com")
    
    test_session.add_all(attendees)
    await test_session.commit()
    
    end_time = time.time()
    creation_time = end_time - start_time
    
    # Should complete within reasonable time (adjust threshold as needed)
    assert creation_time < 5.0  # 5 seconds
    
    # Verify all created
    count_result = await test_session.execute(
        select(func.count(Attendee.id)).where(Attendee.event_id == event.id)
    )
    count = count_result.scalar()
    assert count == 100
```

This comprehensive testing guide ensures that all aspects of the data models are thoroughly validated, from basic CRUD operations to complex business logic and performance characteristics.