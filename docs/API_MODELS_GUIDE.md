# Data Models API Usage Guide

## Overview

This guide provides practical examples of how to use the Speed Dating Application's data models in your API endpoints, business logic, and database operations.

## Basic Model Usage

### Creating and Querying Users

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, OAuthAccount
from app.database import async_session_maker

async def create_user_example():
    async with async_session_maker() as session:
        # Create a new user
        user = User(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            is_verified=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

async def find_user_by_email(email: str):
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
```

### Working with OAuth Accounts

```python
async def add_oauth_account(user_id: uuid.UUID, provider_data: dict):
    async with async_session_maker() as session:
        oauth_account = OAuthAccount(
            user_id=user_id,
            oauth_name=provider_data["provider"],
            account_id=provider_data["account_id"],
            access_token=provider_data["access_token"],
            account_email=provider_data.get("email"),
            account_name=provider_data.get("name")
        )
        session.add(oauth_account)
        await session.commit()
        return oauth_account

async def get_user_oauth_accounts(user_id: uuid.UUID):
    async with async_session_maker() as session:
        result = await session.execute(
            select(OAuthAccount)
            .where(OAuthAccount.user_id == user_id)
            .order_by(OAuthAccount.created_at)
        )
        return result.scalars().all()
```

## Event Management

### Creating Events

```python
from app.models import Event, EventStatus
from datetime import datetime, timedelta

async def create_event(organizer_id: uuid.UUID, event_data: dict):
    async with async_session_maker() as session:
        event = Event(
            name=event_data["name"],
            description=event_data.get("description"),
            location=event_data.get("location"),
            event_date=event_data["event_date"],
            organizer_id=organizer_id,
            max_attendees=event_data.get("max_attendees", 50),
            round_duration_minutes=event_data.get("round_duration", 5),
            break_duration_minutes=event_data.get("break_duration", 2)
        )
        
        # Generate QR secret for the event
        event.generate_qr_secret()
        
        session.add(event)
        await session.commit()
        await session.refresh(event)
        return event

async def publish_event(event_id: uuid.UUID):
    async with async_session_maker() as session:
        event = await session.get(Event, event_id)
        if event and event.has_minimum_attendees:
            event.status = EventStatus.REGISTRATION_OPEN
            event.is_published = True
            await session.commit()
            return True
        return False
```

### Event Queries with Relationships

```python
from sqlalchemy.orm import selectinload

async def get_event_with_attendees(event_id: uuid.UUID):
    async with async_session_maker() as session:
        result = await session.execute(
            select(Event)
            .options(selectinload(Event.attendees))
            .where(Event.id == event_id)
        )
        return result.scalar_one_or_none()

async def get_organizer_events(organizer_id: uuid.UUID):
    async with async_session_maker() as session:
        result = await session.execute(
            select(Event)
            .where(Event.organizer_id == organizer_id)
            .order_by(Event.event_date.desc())
        )
        return result.scalars().all()
```

## Attendee Registration

### Registering Attendees

```python
from app.models import Attendee, AttendeeCategory

async def register_attendee(user_id: uuid.UUID, event_id: uuid.UUID, 
                          registration_data: dict):
    async with async_session_maker() as session:
        # Check if user is already registered
        existing = await session.execute(
            select(Attendee)
            .where(
                Attendee.user_id == user_id,
                Attendee.event_id == event_id
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("User already registered for this event")
        
        attendee = Attendee(
            user_id=user_id,
            event_id=event_id,
            display_name=registration_data["display_name"],
            category=AttendeeCategory(registration_data["category"]),
            age=registration_data.get("age"),
            bio=registration_data.get("bio"),
            dietary_requirements=registration_data.get("dietary_requirements")
        )
        
        # Generate QR token for fast login
        attendee.generate_qr_token()
        
        session.add(attendee)
        await session.commit()
        await session.refresh(attendee)
        return attendee

async def check_in_attendee(attendee_id: uuid.UUID, table_number: int):
    async with async_session_maker() as session:
        attendee = await session.get(Attendee, attendee_id)
        if attendee:
            attendee.checked_in = True
            attendee.check_in_time = datetime.utcnow()
            attendee.table_number = table_number
            await session.commit()
            return attendee
        return None
```

### Category-Based Queries

```python
async def get_attendees_by_category(event_id: uuid.UUID, 
                                  category: AttendeeCategory):
    async with async_session_maker() as session:
        result = await session.execute(
            select(Attendee)
            .where(
                Attendee.event_id == event_id,
                Attendee.category == category,
                Attendee.registration_confirmed == True
            )
            .order_by(Attendee.registered_at)
        )
        return result.scalars().all()

async def get_attendee_statistics(event_id: uuid.UUID):
    async with async_session_maker() as session:
        from sqlalchemy import func
        
        result = await session.execute(
            select(
                Attendee.category,
                func.count(Attendee.id).label("count")
            )
            .where(Attendee.event_id == event_id)
            .group_by(Attendee.category)
        )
        
        stats = {}
        for category, count in result:
            stats[category.value] = count
        return stats
```

## Round and Match Management

### Creating Rounds

```python
from app.models import Round, RoundStatus

async def create_event_rounds(event_id: uuid.UUID, total_rounds: int):
    async with async_session_maker() as session:
        event = await session.get(Event, event_id)
        if not event:
            return []
        
        rounds = []
        for round_num in range(1, total_rounds + 1):
            round_obj = Round(
                event_id=event_id,
                round_number=round_num,
                name=f"Round {round_num}",
                duration_minutes=event.round_duration_minutes,
                break_after_minutes=event.break_duration_minutes
            )
            rounds.append(round_obj)
            session.add(round_obj)
        
        await session.commit()
        return rounds

async def start_round(round_id: uuid.UUID):
    async with async_session_maker() as session:
        round_obj = await session.get(Round, round_id)
        if round_obj and round_obj.status == RoundStatus.PENDING:
            round_obj.start_round()
            await session.commit()
            return round_obj
        return None
```

### Match Creation and Management

```python
from app.models import Match, MatchResponse

async def create_match(event_id: uuid.UUID, round_id: uuid.UUID,
                      attendee1_id: uuid.UUID, attendee2_id: uuid.UUID,
                      table_number: int):
    async with async_session_maker() as session:
        match = Match(
            event_id=event_id,
            round_id=round_id,
            attendee1_id=attendee1_id,
            attendee2_id=attendee2_id,
            table_number=table_number
        )
        session.add(match)
        await session.commit()
        await session.refresh(match)
        return match

async def submit_match_response(match_id: uuid.UUID, attendee_id: uuid.UUID,
                               response: MatchResponse, notes: str = None):
    async with async_session_maker() as session:
        match = await session.get(Match, match_id)
        if match:
            success = match.set_attendee_response(attendee_id, response, notes)
            if success:
                await session.commit()
                return match
        return None

async def get_mutual_matches(event_id: uuid.UUID):
    async with async_session_maker() as session:
        result = await session.execute(
            select(Match)
            .options(
                selectinload(Match.attendee1),
                selectinload(Match.attendee2)
            )
            .where(
                Match.event_id == event_id,
                Match.attendee1_response == MatchResponse.YES,
                Match.attendee2_response == MatchResponse.YES
            )
        )
        return result.scalars().all()
```

## QR Code Authentication

### QR Token Management

```python
from app.models import QRLogin

async def create_qr_login_token(attendee_id: uuid.UUID, event_id: uuid.UUID,
                               expire_hours: int = 24):
    async with async_session_maker() as session:
        # Get attendee to link user
        attendee = await session.get(Attendee, attendee_id)
        if not attendee:
            return None
        
        qr_login = QRLogin.create_for_attendee(
            attendee_id=attendee_id,
            event_id=event_id,
            user_id=attendee.user_id,
            expire_hours=expire_hours
        )
        
        session.add(qr_login)
        await session.commit()
        await session.refresh(qr_login)
        return qr_login

async def validate_qr_token(token: str, event_id: uuid.UUID):
    async with async_session_maker() as session:
        # Find token by hash
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        result = await session.execute(
            select(QRLogin)
            .options(selectinload(QRLogin.attendee))
            .where(
                QRLogin.token_hash == token_hash,
                QRLogin.event_id == event_id
            )
        )
        qr_login = result.scalar_one_or_none()
        
        if qr_login and qr_login.is_valid:
            return qr_login
        return None

async def use_qr_token(token: str, event_id: uuid.UUID, 
                      ip_address: str = None):
    async with async_session_maker() as session:
        qr_login = await validate_qr_token(token, event_id)
        if qr_login:
            success = qr_login.use_token(ip_address=ip_address)
            if success:
                await session.commit()
                return qr_login.attendee
        return None
```

## Advanced Queries

### Complex Relationship Queries

```python
async def get_event_dashboard_data(event_id: uuid.UUID):
    """Get comprehensive event data for admin dashboard"""
    async with async_session_maker() as session:
        # Main event with all relationships
        event_result = await session.execute(
            select(Event)
            .options(
                selectinload(Event.attendees),
                selectinload(Event.rounds).selectinload(Round.matches),
                selectinload(Event.organizer)
            )
            .where(Event.id == event_id)
        )
        event = event_result.scalar_one_or_none()
        
        if not event:
            return None
        
        # Get match statistics
        match_stats = await session.execute(
            select(
                func.count(Match.id).label("total_matches"),
                func.sum(
                    case(
                        (Match.is_completed == True, 1),
                        else_=0
                    )
                ).label("completed_matches"),
                func.sum(
                    case(
                        (
                            and_(
                                Match.attendee1_response == MatchResponse.YES,
                                Match.attendee2_response == MatchResponse.YES
                            ), 1
                        ),
                        else_=0
                    )
                ).label("mutual_matches")
            )
            .where(Match.event_id == event_id)
        )
        stats = match_stats.first()
        
        return {
            "event": event,
            "total_attendees": len(event.attendees),
            "checked_in": sum(1 for a in event.attendees if a.checked_in),
            "total_rounds": len(event.rounds),
            "active_round": next(
                (r for r in event.rounds if r.is_active), None
            ),
            "match_statistics": {
                "total": stats.total_matches or 0,
                "completed": stats.completed_matches or 0,
                "mutual": stats.mutual_matches or 0
            }
        }

async def get_attendee_matches_summary(attendee_id: uuid.UUID):
    """Get all matches for an attendee with responses"""
    async with async_session_maker() as session:
        # Matches where attendee is participant 1
        matches1 = await session.execute(
            select(Match)
            .options(selectinload(Match.attendee2))
            .where(Match.attendee1_id == attendee_id)
        )
        
        # Matches where attendee is participant 2  
        matches2 = await session.execute(
            select(Match)
            .options(selectinload(Match.attendee1))
            .where(Match.attendee2_id == attendee_id)
        )
        
        all_matches = list(matches1.scalars()) + list(matches2.scalars())
        
        summary = {
            "total_matches": len(all_matches),
            "completed_responses": sum(1 for m in all_matches 
                                     if m.get_attendee_response(attendee_id) != MatchResponse.NO_RESPONSE),
            "mutual_matches": sum(1 for m in all_matches if m.is_mutual_match),
            "matches": []
        }
        
        for match in all_matches:
            other_attendee = (match.attendee2 if match.attendee1_id == attendee_id 
                            else match.attendee1)
            my_response = match.get_attendee_response(attendee_id)
            their_response = match.get_attendee_response(
                match.get_other_attendee_id(attendee_id)
            )
            
            summary["matches"].append({
                "match_id": match.id,
                "other_attendee": {
                    "id": other_attendee.id,
                    "name": other_attendee.display_name,
                    "category": other_attendee.category
                },
                "my_response": my_response,
                "their_response": their_response,
                "is_mutual": match.is_mutual_match,
                "table_number": match.table_number,
                "round_number": match.round.round_number if match.round else None
            })
        
        return summary
```

## Model Validation and Business Logic

### Custom Validation Examples

```python
from sqlalchemy.exc import IntegrityError

async def safe_attendee_registration(user_id: uuid.UUID, event_id: uuid.UUID,
                                   registration_data: dict):
    """Register attendee with comprehensive validation"""
    async with async_session_maker() as session:
        try:
            # Check event capacity
            event = await session.get(Event, event_id)
            if not event:
                raise ValueError("Event not found")
            
            if not event.is_registration_open:
                raise ValueError("Registration is closed")
            
            if event.is_full:
                raise ValueError("Event is at maximum capacity")
            
            # Check for duplicate registration
            existing = await session.execute(
                select(Attendee).where(
                    Attendee.user_id == user_id,
                    Attendee.event_id == event_id
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError("Already registered for this event")
            
            # Create attendee
            attendee = Attendee(
                user_id=user_id,
                event_id=event_id,
                **registration_data
            )
            attendee.generate_qr_token()
            
            session.add(attendee)
            await session.commit()
            await session.refresh(attendee)
            
            return {"success": True, "attendee": attendee}
            
        except IntegrityError as e:
            await session.rollback()
            return {"success": False, "error": "Database constraint violation"}
        except ValueError as e:
            return {"success": False, "error": str(e)}

async def validate_match_compatibility(attendee1_id: uuid.UUID, 
                                     attendee2_id: uuid.UUID):
    """Check if two attendees can be matched"""
    async with async_session_maker() as session:
        attendee1 = await session.get(Attendee, attendee1_id)
        attendee2 = await session.get(Attendee, attendee2_id)
        
        if not attendee1 or not attendee2:
            return False
        
        return attendee1.can_match_with(attendee2)
```

## Performance Optimization Examples

### Bulk Operations

```python
async def bulk_create_matches(round_id: uuid.UUID, match_pairs: list):
    """Efficiently create multiple matches"""
    async with async_session_maker() as session:
        matches = []
        for i, (attendee1_id, attendee2_id) in enumerate(match_pairs, 1):
            match = Match(
                round_id=round_id,
                attendee1_id=attendee1_id,
                attendee2_id=attendee2_id,
                table_number=i
            )
            matches.append(match)
        
        session.add_all(matches)
        await session.commit()
        return matches

async def bulk_update_attendee_checkin(attendee_ids: list[uuid.UUID]):
    """Bulk check-in attendees"""
    async with async_session_maker() as session:
        await session.execute(
            update(Attendee)
            .where(Attendee.id.in_(attendee_ids))
            .values(
                checked_in=True,
                check_in_time=datetime.utcnow()
            )
        )
        await session.commit()
```

### Optimized Queries

```python
async def get_event_matches_optimized(event_id: uuid.UUID):
    """Get all matches with minimal database queries"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Match)
            .options(
                selectinload(Match.attendee1),
                selectinload(Match.attendee2),
                selectinload(Match.round)
            )
            .where(Match.event_id == event_id)
            .order_by(Match.round_id, Match.table_number)
        )
        return result.scalars().all()
```

This guide provides comprehensive examples of how to effectively use the Speed Dating Application's data models in real-world scenarios, demonstrating best practices for database operations, relationship handling, and performance optimization.