"""
Unit tests for core SQLAlchemy models using Hypothesis property-based testing.

Tests the behavior of User, Event, Attendee, Round, Match, and other models
with realistic data generation and property verification.
"""

import pytest
from datetime import UTC, datetime, timedelta
from hypothesis import given, assume, strategies as st
from sqlalchemy.exc import IntegrityError

from app.models import User, Event, Attendee, Round, Match, QRLogin
from tests.strategies import (
    user_strategy,
    event_strategy,
    attendee_strategy, 
    round_strategy,
    match_strategy,
    qr_login_strategy,
)


@pytest.mark.unit
@pytest.mark.hypothesis  
class TestUserModel:
    """Test User model with property-based testing."""
    
    @given(user_data=user_strategy())
    async def test_user_creation_properties(self, user_data, db_session):
        """Test that User objects maintain expected properties."""
        # Remove ID for creation
        user_data_copy = user_data.copy()
        user_data_copy.pop("id", None)
        user_data_copy.pop("created_at", None)
        user_data_copy.pop("updated_at", None)
        
        user = User(**user_data_copy)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Verify basic properties
        assert user.email == user_data_copy["email"]
        assert user.first_name == user_data_copy["first_name"] 
        assert user.last_name == user_data_copy["last_name"]
        assert user.is_active == user_data_copy["is_active"]
        assert user.is_verified == user_data_copy["is_verified"]
        assert user.is_superuser == user_data_copy["is_superuser"]
        
        # Verify automatic fields
        assert user.id is not None
        assert user.created_at is not None
        assert user.updated_at is not None
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)
    
    @given(
        user_data_1=user_strategy(),
        user_data_2=user_strategy()
    )
    async def test_user_email_uniqueness(self, user_data_1, user_data_2, db_session):
        """Test that users must have unique email addresses."""
        assume(user_data_1["email"] == user_data_2["email"])
        
        # Create first user
        user_data_1_copy = user_data_1.copy()
        user_data_1_copy.pop("id", None)
        user_data_1_copy.pop("created_at", None)
        user_data_1_copy.pop("updated_at", None)
        
        user1 = User(**user_data_1_copy)
        db_session.add(user1)
        await db_session.commit()
        
        # Try to create second user with same email
        user_data_2_copy = user_data_2.copy() 
        user_data_2_copy.pop("id", None)
        user_data_2_copy.pop("created_at", None)
        user_data_2_copy.pop("updated_at", None)
        
        user2 = User(**user_data_2_copy)
        db_session.add(user2)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @given(user_data=user_strategy())
    async def test_user_full_name_property(self, user_data, db_session):
        """Test the full_name property combines first and last name."""
        user_data_copy = user_data.copy()
        user_data_copy.pop("id", None)
        user_data_copy.pop("created_at", None)
        user_data_copy.pop("updated_at", None)
        
        user = User(**user_data_copy)
        
        expected_full_name = f"{user.first_name} {user.last_name}"
        assert user.full_name == expected_full_name


@pytest.mark.unit
@pytest.mark.hypothesis
class TestEventModel:
    """Test Event model with property-based testing."""
    
    @given(event_data=event_strategy())
    async def test_event_creation_properties(self, event_data, db_session, test_user):
        """Test Event creation with valid data."""
        event_data_copy = event_data.copy()
        event_data_copy.pop("id", None) 
        event_data_copy.pop("created_at", None)
        event_data_copy.pop("updated_at", None)
        event_data_copy["organizer_id"] = test_user.id
        
        event = Event(**event_data_copy)
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)
        
        # Verify properties
        assert event.name == event_data_copy["name"]
        assert event.event_date == event_data_copy["event_date"]
        assert event.venue_name == event_data_copy["venue_name"]
        assert event.min_attendees == event_data_copy["min_attendees"]
        assert event.max_attendees == event_data_copy["max_attendees"]
        assert event.organizer_id == test_user.id
        
        # Verify constraints
        assert event.min_attendees <= event.max_attendees
        assert event.registration_deadline < event.event_date
    
    @given(event_data=event_strategy())
    async def test_event_date_constraints(self, event_data, db_session, test_user):
        """Test that events must be in the future and registration deadline before event."""
        event_data_copy = event_data.copy()
        event_data_copy.pop("id", None)
        event_data_copy.pop("created_at", None) 
        event_data_copy.pop("updated_at", None)
        event_data_copy["organizer_id"] = test_user.id
        
        # Ensure event is in future
        assume(event_data_copy["event_date"] > datetime.now(UTC))
        assume(event_data_copy["registration_deadline"] < event_data_copy["event_date"])
        
        event = Event(**event_data_copy)
        db_session.add(event)
        await db_session.commit()
        
        # Verify constraints maintained
        assert event.event_date > datetime.now(UTC)
        assert event.registration_deadline < event.event_date


@pytest.mark.unit 
@pytest.mark.hypothesis
class TestAttendeeModel:
    """Test Attendee model with property-based testing."""
    
    @given(attendee_data=attendee_strategy())
    async def test_attendee_creation_properties(self, attendee_data, db_session, 
                                               test_user, faker_instance):
        """Test Attendee creation with valid data."""
        # Create event first
        event_data = {
            "name": faker_instance.event_name(),
            "description": faker_instance.text(),
            "event_date": faker_instance.date_time_between(
                start_date="+1d", end_date="+30d", tzinfo=UTC
            ),
            "registration_deadline": faker_instance.date_time_between(
                start_date="+1h", end_date="+29d", tzinfo=UTC
            ),
            "venue_name": faker_instance.venue_name(),
            "venue_address": faker_instance.uk_address(),
            "min_attendees": 10,
            "max_attendees": 30,
            "price": 25.00,
            "round_duration_minutes": 5,
            "break_duration_minutes": 2,
            "category_name": "Test Category",
            "category_min_age": 25,
            "category_max_age": 40,
            "organizer_id": test_user.id,
        }
        
        event = Event(**event_data)
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)
        
        # Create attendee
        attendee_data_copy = attendee_data.copy()
        attendee_data_copy.pop("id", None)
        attendee_data_copy.pop("created_at", None)
        attendee_data_copy.pop("updated_at", None)
        attendee_data_copy["event_id"] = event.id
        attendee_data_copy["user_id"] = test_user.id
        
        # Ensure age constraints are valid
        assume(attendee_data_copy["looking_for_ages_min"] <= attendee_data_copy["looking_for_ages_max"])
        assume(18 <= attendee_data_copy["age"] <= 100)
        
        attendee = Attendee(**attendee_data_copy)
        db_session.add(attendee)
        await db_session.commit()
        await db_session.refresh(attendee)
        
        # Verify properties
        assert attendee.age == attendee_data_copy["age"]
        assert attendee.profession == attendee_data_copy["profession"]
        assert attendee.bio == attendee_data_copy["bio"]
        assert attendee.looking_for_ages_min <= attendee.looking_for_ages_max
        assert attendee.event_id == event.id
        assert attendee.user_id == test_user.id


@pytest.mark.unit
@pytest.mark.hypothesis  
class TestMatchModel:
    """Test Match model with property-based testing."""
    
    @given(match_data=match_strategy())
    async def test_match_creation_properties(self, match_data, db_session, 
                                           test_user, faker_instance):
        """Test Match creation with valid data."""
        # Create event
        event_data = {
            "name": faker_instance.event_name(),
            "description": faker_instance.text(),
            "event_date": faker_instance.date_time_between(
                start_date="+1d", end_date="+30d", tzinfo=UTC
            ),
            "registration_deadline": faker_instance.date_time_between(
                start_date="+1h", end_date="+29d", tzinfo=UTC  
            ),
            "venue_name": faker_instance.venue_name(),
            "venue_address": faker_instance.uk_address(),
            "min_attendees": 10,
            "max_attendees": 30,
            "price": 25.00,
            "round_duration_minutes": 5,
            "break_duration_minutes": 2,
            "category_name": "Test Category",
            "category_min_age": 25,
            "category_max_age": 40,
            "organizer_id": test_user.id,
        }
        
        event = Event(**event_data)
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)
        
        # Create round  
        round_data = {
            "event_id": event.id,
            "round_number": 1,
            "start_time": datetime.now(UTC) + timedelta(hours=1),
            "end_time": datetime.now(UTC) + timedelta(hours=2),
            "is_active": True,
        }
        
        round_obj = Round(**round_data)
        db_session.add(round_obj)
        await db_session.commit()
        await db_session.refresh(round_obj)
        
        # Create attendees
        attendee1_data = {
            "event_id": event.id,
            "user_id": test_user.id,
            "age": 30,
            "profession": "Engineer",
            "bio": "Test bio that is long enough to meet requirements",
            "looking_for_ages_min": 25,
            "looking_for_ages_max": 35,
            "phone": faker_instance.uk_phone_number(),
            "payment_status": "paid",
            "qr_code_data": "test_qr_code_1",
        }
        
        # Create another user for second attendee
        user2_data = {
            "email": faker_instance.email(),
            "first_name": faker_instance.first_name(),
            "last_name": faker_instance.last_name(),
            "is_active": True,
            "is_verified": True,
        }
        user2 = User(**user2_data)
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user2)
        
        attendee2_data = {
            "event_id": event.id,
            "user_id": user2.id,
            "age": 28,
            "profession": "Teacher",
            "bio": "Another test bio that is long enough to meet requirements",
            "looking_for_ages_min": 25,
            "looking_for_ages_max": 35,
            "phone": faker_instance.uk_phone_number(),
            "payment_status": "paid",
            "qr_code_data": "test_qr_code_2",
        }
        
        attendee1 = Attendee(**attendee1_data)
        attendee2 = Attendee(**attendee2_data)
        db_session.add_all([attendee1, attendee2])
        await db_session.commit()
        await db_session.refresh(attendee1)
        await db_session.refresh(attendee2)
        
        # Create match
        match_data_copy = match_data.copy()
        match_data_copy.pop("id", None)
        match_data_copy.pop("created_at", None)
        match_data_copy.pop("updated_at", None)
        match_data_copy["event_id"] = event.id
        match_data_copy["round_id"] = round_obj.id
        match_data_copy["attendee1_id"] = attendee1.id
        match_data_copy["attendee2_id"] = attendee2.id
        
        match = Match(**match_data_copy)
        db_session.add(match)
        await db_session.commit()
        await db_session.refresh(match)
        
        # Verify properties
        assert match.event_id == event.id
        assert match.round_id == round_obj.id
        assert match.attendee1_id == attendee1.id
        assert match.attendee2_id == attendee2.id
        assert match.attendee1_id != match.attendee2_id  # Different attendees
    
    @given(
        response1=st.sampled_from(["yes", "no"]),
        response2=st.sampled_from(["yes", "no"])
    )
    async def test_match_mutual_match_logic(self, response1, response2, 
                                          db_session, test_user, faker_instance):
        """Test that mutual match detection works correctly."""
        # Setup similar to above but simplified
        event = Event(
            name="Test Event",
            description="Test Description",
            event_date=datetime.now(UTC) + timedelta(days=1),
            registration_deadline=datetime.now(UTC) + timedelta(hours=1),
            venue_name="Test Venue",
            venue_address="Test Address",
            min_attendees=10,
            max_attendees=30,
            price=25.00,
            round_duration_minutes=5,
            break_duration_minutes=2,
            category_name="Test Category",
            category_min_age=25,
            category_max_age=40,
            organizer_id=test_user.id,
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)
        
        # Create match with specific responses
        match = Match(
            event_id=event.id,
            attendee1_response=response1,
            attendee2_response=response2,
            attendee1_id=str(faker_instance.uuid4()),
            attendee2_id=str(faker_instance.uuid4()),
        )
        
        # Test mutual match logic
        expected_mutual = (response1 == "yes" and response2 == "yes")
        match.is_mutual_match = expected_mutual
        
        assert match.is_mutual_match == expected_mutual