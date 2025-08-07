"""
Core Hypothesis strategies for Speed Dating domain objects.

Provides strategies for generating Users, Events, Attendees, Rounds, Matches,
and other core business entities with realistic constraints and relationships.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from hypothesis import strategies as st

from tests.fixtures.faker_providers import setup_faker_providers

# Set up Faker with our custom providers
fake = setup_faker_providers()

# Basic strategies
uuid_strategy = st.uuids().map(str)
email_strategy = st.from_regex(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    fullmatch=True
).filter(lambda x: len(x) <= 100)

phone_strategy = st.from_regex(
    r"^(\+44|0)[1-9]\d{8,10}$",
    fullmatch=True
)

# Date strategies
future_datetime_strategy = st.datetimes(
    min_value=datetime.now(UTC) + timedelta(hours=1),
    max_value=datetime.now(UTC) + timedelta(days=365),
    timezones=st.just(UTC)
)

past_datetime_strategy = st.datetimes(
    min_value=datetime.now(UTC) - timedelta(days=365),
    max_value=datetime.now(UTC) - timedelta(hours=1),
    timezones=st.just(UTC)
)

# Text strategies
name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127),
    min_size=2,
    max_size=50
).filter(lambda x: x.strip() and x.isalpha())

bio_strategy = st.text(
    min_size=50,
    max_size=500
).filter(lambda x: len(x.strip()) >= 50)

profession_strategy = st.sampled_from([
    "Software Engineer", "Teacher", "Nurse", "Doctor", "Lawyer",
    "Accountant", "Marketing Manager", "Designer", "Consultant",
    "Project Manager", "Sales Executive", "HR Manager", "Architect"
])

# Age and category strategies
age_strategy = st.integers(min_value=18, max_value=75)

category_name_strategy = st.sampled_from([
    "Young Professionals", "Thirty Something", "Mature Singles",
    "Silver Singles", "Graduate Speed Dating", "Creative Professionals"
])


@st.composite
def user_strategy(draw, 
                  is_active: Optional[bool] = None,
                  is_verified: Optional[bool] = None,
                  is_superuser: Optional[bool] = None,
                  is_organizer: Optional[bool] = None):
    """Generate realistic User data."""
    return {
        "id": draw(uuid_strategy),
        "email": draw(email_strategy),
        "first_name": draw(name_strategy),
        "last_name": draw(name_strategy),
        "is_active": is_active if is_active is not None else draw(st.booleans()),
        "is_verified": is_verified if is_verified is not None else draw(st.booleans()),
        "is_superuser": is_superuser if is_superuser is not None else draw(st.booleans()),
        "is_organizer": is_organizer if is_organizer is not None else draw(st.booleans()),
        "created_at": draw(past_datetime_strategy),
        "updated_at": draw(past_datetime_strategy),
    }


@st.composite
def event_strategy(draw,
                   organizer_id: Optional[str] = None,
                   min_attendees: Optional[int] = None,
                   max_attendees: Optional[int] = None):
    """Generate realistic Event data."""
    max_att = max_attendees or draw(st.integers(min_value=10, max_value=50))
    min_att = min_attendees or draw(st.integers(min_value=6, max_value=max_att))
    
    event_date = draw(future_datetime_strategy)
    registration_deadline = event_date - timedelta(hours=draw(st.integers(min_value=2, max_value=72)))
    
    return {
        "id": draw(uuid_strategy),
        "name": fake.event_name(),
        "description": draw(st.text(min_size=100, max_size=1000)),
        "event_date": event_date,
        "registration_deadline": registration_deadline,
        "venue_name": fake.venue_name(),
        "venue_address": fake.uk_address(),
        "min_attendees": min_att,
        "max_attendees": max_att,
        "price": draw(st.decimals(min_value=15, max_value=85, places=2)),
        "round_duration_minutes": fake.round_duration(),
        "break_duration_minutes": draw(st.integers(min_value=1, max_value=5)),
        "category_name": draw(category_name_strategy),
        "category_min_age": draw(st.integers(min_value=18, max_value=35)),
        "category_max_age": draw(st.integers(min_value=25, max_value=75)),
        "is_active": draw(st.booleans()),
        "organizer_id": organizer_id or draw(uuid_strategy),
        "created_at": draw(past_datetime_strategy),
        "updated_at": draw(past_datetime_strategy),
    }


@st.composite  
def attendee_strategy(draw,
                      event_id: Optional[str] = None,
                      user_id: Optional[str] = None):
    """Generate realistic Attendee data."""
    age = draw(age_strategy)
    
    return {
        "id": draw(uuid_strategy),
        "event_id": event_id or draw(uuid_strategy),
        "user_id": user_id or draw(uuid_strategy),
        "age": age,
        "profession": draw(profession_strategy),
        "bio": fake.bio(),
        "looking_for_ages_min": max(18, age - draw(st.integers(min_value=0, max_value=10))),
        "looking_for_ages_max": min(75, age + draw(st.integers(min_value=5, max_value=15))),
        "phone": fake.uk_phone_number(),
        "fetlife_username": fake.fetlife_username(),
        "payment_status": draw(st.sampled_from(["pending", "paid", "refunded"])),
        "check_in_time": draw(st.one_of(st.none(), past_datetime_strategy)),
        "qr_code_data": draw(st.text(min_size=20, max_size=50)),
        "created_at": draw(past_datetime_strategy),
        "updated_at": draw(past_datetime_strategy),
    }


@st.composite
def round_strategy(draw,
                   event_id: Optional[str] = None,
                   round_number: Optional[int] = None):
    """Generate realistic Round data."""
    start_time = draw(future_datetime_strategy)
    duration = draw(st.integers(min_value=3, max_value=8))
    end_time = start_time + timedelta(minutes=duration)
    
    return {
        "id": draw(uuid_strategy), 
        "event_id": event_id or draw(uuid_strategy),
        "round_number": round_number or draw(st.integers(min_value=1, max_value=20)),
        "start_time": start_time,
        "end_time": end_time,
        "is_active": draw(st.booleans()),
        "created_at": draw(past_datetime_strategy),
    }


@st.composite
def match_strategy(draw,
                   event_id: Optional[str] = None,
                   round_id: Optional[str] = None,
                   attendee1_id: Optional[str] = None,
                   attendee2_id: Optional[str] = None):
    """Generate realistic Match data."""
    # Ensure different attendees
    att1_id = attendee1_id or draw(uuid_strategy)
    att2_id = attendee2_id or draw(uuid_strategy)
    while att2_id == att1_id:
        att2_id = draw(uuid_strategy)
    
    return {
        "id": draw(uuid_strategy),
        "event_id": event_id or draw(uuid_strategy), 
        "round_id": round_id or draw(uuid_strategy),
        "attendee1_id": att1_id,
        "attendee2_id": att2_id,
        "attendee1_response": draw(st.sampled_from([None, "yes", "no"])),
        "attendee2_response": draw(st.sampled_from([None, "yes", "no"])),
        "attendee1_rating": draw(st.one_of(st.none(), st.integers(min_value=1, max_value=5))),
        "attendee2_rating": draw(st.one_of(st.none(), st.integers(min_value=1, max_value=5))),
        "is_mutual_match": draw(st.booleans()),
        "created_at": draw(past_datetime_strategy),
        "updated_at": draw(past_datetime_strategy),
    }


@st.composite
def qr_login_strategy(draw,
                      attendee_id: Optional[str] = None):
    """Generate realistic QR Login data."""
    expires_at = datetime.now(UTC) + timedelta(hours=draw(st.integers(min_value=1, max_value=24)))
    
    return {
        "id": draw(uuid_strategy),
        "attendee_id": attendee_id or draw(uuid_strategy),
        "token": draw(st.text(min_size=32, max_size=64)),
        "expires_at": expires_at,
        "used_at": draw(st.one_of(st.none(), past_datetime_strategy)),
        "ip_address": draw(st.ip_addresses().map(str)),
        "user_agent": draw(st.text(min_size=20, max_size=200)),
        "is_active": draw(st.booleans()),
        "created_at": draw(past_datetime_strategy),
    }


# Composite strategies for realistic relationships
@st.composite
def event_with_attendees_strategy(draw, num_attendees: int = 5):
    """Generate an event with realistic attendees."""
    event_data = draw(event_strategy())
    event_id = event_data["id"]
    
    attendees = []
    for _ in range(num_attendees):
        attendee_data = draw(attendee_strategy(event_id=event_id))
        attendees.append(attendee_data)
    
    return {
        "event": event_data,
        "attendees": attendees
    }


@st.composite
def complete_speed_dating_scenario_strategy(draw):
    """Generate a complete speed dating scenario with all related entities."""
    # Create organizer
    organizer = draw(user_strategy(is_organizer=True, is_active=True))
    
    # Create event
    event_data = draw(event_strategy(organizer_id=organizer["id"]))
    event_id = event_data["id"]
    
    # Create attendees
    num_attendees = draw(st.integers(min_value=4, max_value=12))
    attendees = []
    for _ in range(num_attendees):
        user_data = draw(user_strategy(is_active=True))
        attendee_data = draw(attendee_strategy(event_id=event_id, user_id=user_data["id"]))
        attendees.append({
            "user": user_data,
            "attendee": attendee_data
        })
    
    # Create rounds
    num_rounds = min(num_attendees // 2, draw(st.integers(min_value=2, max_value=8)))
    rounds = []
    for i in range(num_rounds):
        round_data = draw(round_strategy(event_id=event_id, round_number=i+1))
        rounds.append(round_data)
    
    # Create matches
    matches = []
    if len(attendees) >= 2 and len(rounds) > 0:
        for round_data in rounds[:2]:  # Only generate matches for first 2 rounds
            for i in range(0, len(attendees)-1, 2):
                if i+1 < len(attendees):
                    match_data = draw(match_strategy(
                        event_id=event_id,
                        round_id=round_data["id"],
                        attendee1_id=attendees[i]["attendee"]["id"],
                        attendee2_id=attendees[i+1]["attendee"]["id"]
                    ))
                    matches.append(match_data)
    
    return {
        "organizer": organizer,
        "event": event_data,
        "attendees": attendees,
        "rounds": rounds,
        "matches": matches
    }