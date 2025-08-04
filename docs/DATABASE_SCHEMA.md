# Speed Dating Application - Database Schema Documentation

## Overview

The Speed Dating Application uses a comprehensive database schema designed to support OAuth2 authentication, QR code-based fast login, category-based matching, and complete event management. The schema is built using SQLAlchemy with async support and integrates with FastAPI-Users for authentication.

## Database Architecture

### Technology Stack
- **ORM**: SQLAlchemy 2.0+ with async support
- **Database**: SQLite (development) / PostgreSQL (production)
- **Authentication**: FastAPI-Users with OAuth2 integration
- **Migrations**: Alembic (future implementation)

### Design Principles
- **Normalization**: 3NF compliance with optimized relationships
- **Security**: Token hashing, audit trails, and secure session management
- **Scalability**: UUID primary keys and efficient indexing
- **Flexibility**: Enum-based categorization and configurable matching

---

## Core Models

### 1. User Model

**Table**: `user`  
**Purpose**: Core user authentication and profile management with OAuth2 support

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | Primary Key | Unique user identifier |
| `email` | String(320) | Unique, Not Null | User's email address (FastAPI-Users) |
| `hashed_password` | String(1024) | Nullable | Hashed password (FastAPI-Users) |
| `is_active` | Boolean | Default: True | Account activation status |
| `is_superuser` | Boolean | Default: False | Administrative privileges |
| `is_verified` | Boolean | Default: False | Email verification status |
| `first_name` | String(100) | Nullable | User's first name |
| `last_name` | String(100) | Nullable | User's last name |
| `display_name` | String(200) | Nullable | Preferred display name |
| `is_organizer` | Boolean | Default: False | Event organization privileges |
| `created_at` | DateTime(TZ) | Auto-generated | Account creation timestamp |
| `updated_at` | DateTime(TZ) | Auto-updated | Last modification timestamp |
| `last_login` | DateTime(TZ) | Nullable | Last login timestamp |
| `profile_picture_url` | String(500) | Nullable | Profile image URL |
| `bio` | String(500) | Nullable | User biography |

#### Relationships
- **oauth_accounts**: One-to-Many → `OAuthAccount`
- **attendee_profiles**: One-to-Many → `Attendee`
- **organized_events**: One-to-Many → `Event`
- **qr_logins**: One-to-Many → `QRLogin`

#### Properties
- `full_name`: Computed property combining first_name and last_name
- Inherits all FastAPI-Users base functionality

---

### 2. OAuthAccount Model

**Table**: `oauth_account`  
**Purpose**: Store OAuth2 provider information for multiple authentication methods

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | Primary Key | Unique OAuth account identifier |
| `user_id` | UUID | Foreign Key | Reference to User |
| `oauth_name` | String(100) | Not Null | Provider name (google, facebook) |
| `access_token` | String(1024) | Not Null | OAuth access token |
| `refresh_token` | String(1024) | Nullable | OAuth refresh token |
| `account_id` | String(320) | Not Null | Provider account identifier |
| `account_email` | String(320) | Nullable | Email from OAuth provider |
| `account_name` | String(200) | Nullable | Name from OAuth provider |
| `account_picture` | String(500) | Nullable | Profile picture from provider |
| `created_at` | DateTime(TZ) | Auto-generated | Account creation timestamp |
| `updated_at` | DateTime(TZ) | Auto-updated | Last update timestamp |
| `last_used` | DateTime(TZ) | Nullable | Last authentication timestamp |

#### Relationships
- **user**: Many-to-One → `User`

#### Indexes
- `oauth_name + account_id` (Unique composite)
- `user_id`

---

### 3. Event Model

**Table**: `event`  
**Purpose**: Manage speed dating events with comprehensive configuration

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | Primary Key | Unique event identifier |
| `name` | String(200) | Not Null | Event name |
| `description` | Text | Nullable | Event description |
| `location` | String(500) | Nullable | Event venue |
| `event_date` | DateTime(TZ) | Not Null | Event date and time |
| `registration_deadline` | DateTime(TZ) | Nullable | Registration cutoff |
| `round_duration_minutes` | Integer | Default: 5 | Minutes per round |
| `break_duration_minutes` | Integer | Default: 2 | Minutes between rounds |
| `total_rounds` | Integer | Nullable | Total number of rounds |
| `max_attendees` | Integer | Default: 100 | Maximum capacity |
| `min_attendees` | Integer | Default: 6 | Minimum for event |
| `status` | EventStatus | Default: DRAFT | Event status |
| `is_published` | Boolean | Default: False | Public visibility |
| `registration_open` | Boolean | Default: True | Registration availability |
| `qr_enabled` | Boolean | Default: True | QR code functionality |
| `qr_secret_key` | String(100) | Nullable | QR encryption key |
| `ticket_price` | Integer | Nullable | Price in cents |
| `currency` | String(3) | Default: USD | Currency code |
| `created_at` | DateTime(TZ) | Auto-generated | Creation timestamp |
| `updated_at` | DateTime(TZ) | Auto-updated | Update timestamp |
| `organizer_id` | UUID | Foreign Key | Event organizer |

#### Enums

**EventStatus**:
- `DRAFT`: Event being planned
- `REGISTRATION_OPEN`: Accepting registrations
- `REGISTRATION_CLOSED`: Registration ended
- `ACTIVE`: Event in progress
- `COMPLETED`: Event finished
- `CANCELLED`: Event cancelled

#### Relationships
- **organizer**: Many-to-One → `User`
- **attendees**: One-to-Many → `Attendee`
- **rounds**: One-to-Many → `Round` (ordered by round_number)
- **matches**: One-to-Many → `Match`
- **qr_logins**: One-to-Many → `QRLogin`

#### Properties
- `is_active`: Check if event is currently running
- `is_registration_open`: Validate registration availability
- `attendee_count`: Current number of attendees
- `is_full`: Check capacity limits
- `has_minimum_attendees`: Validate minimum requirements

#### Methods
- `generate_qr_secret()`: Create new QR encryption key
- `get_event_duration()`: Calculate total event time

---

### 4. Attendee Model

**Table**: `attendee`  
**Purpose**: Link users to events with category and preference information

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | Primary Key | Unique attendee identifier |
| `display_name` | String(200) | Not Null | Name for event |
| `age` | Integer | Nullable | Attendee age |
| `bio` | Text | Nullable | Personal description |
| `category` | AttendeeCategory | Not Null | Matching category |
| `checked_in` | Boolean | Default: False | Event check-in status |
| `check_in_time` | DateTime(TZ) | Nullable | Check-in timestamp |
| `table_number` | Integer | Nullable | Assigned table |
| `qr_token` | String(100) | Unique | QR login token |
| `qr_generated_at` | DateTime(TZ) | Nullable | QR generation time |
| `qr_last_used` | DateTime(TZ) | Nullable | Last QR usage |
| `contact_email` | String(320) | Nullable | Contact email |
| `contact_phone` | String(20) | Nullable | Contact phone |
| `registration_confirmed` | Boolean | Default: False | Registration status |
| `payment_confirmed` | Boolean | Default: True | Payment status |
| `dietary_requirements` | String(500) | Nullable | Special dietary needs |
| `special_notes` | Text | Nullable | Additional notes |
| `registered_at` | DateTime(TZ) | Auto-generated | Registration timestamp |
| `updated_at` | DateTime(TZ) | Auto-updated | Update timestamp |
| `user_id` | UUID | Foreign Key | Reference to User |
| `event_id` | UUID | Foreign Key | Reference to Event |

#### Enums

**AttendeeCategory**:
- `TOP_MALE`: Top male category
- `TOP_FEMALE`: Top female category  
- `BOTTOM_MALE`: Bottom male category
- `BOTTOM_FEMALE`: Bottom female category

#### Relationships
- **user**: Many-to-One → `User`
- **event**: Many-to-One → `Event`
- **matches_as_attendee1**: One-to-Many → `Match`
- **matches_as_attendee2**: One-to-Many → `Match`

#### Properties
- `all_matches`: Combined list of all matches

#### Methods
- `generate_qr_token()`: Create unique QR access token
- `is_interested_in_category(category)`: Check matching preferences
- `can_match_with(other_attendee)`: Validate matching compatibility

#### Indexes
- `user_id + event_id` (Unique composite)
- `qr_token` (Unique)
- `category`

---

### 5. AttendeePreference Model

**Table**: `attendee_preference`  
**Purpose**: Explicit preference system for flexible matching

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `attendee_id` | UUID | Primary Key, FK | Reference to Attendee |
| `preferred_category` | AttendeeCategory | Primary Key | Preferred category |
| `preference_strength` | Integer | Default: 3 | Preference intensity (1-5) |
| `created_at` | DateTime(TZ) | Auto-generated | Creation timestamp |

#### Relationships
- **attendee**: Many-to-One → `Attendee`

---

### 6. Round Model

**Table**: `round`  
**Purpose**: Manage individual rounds within events

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | Primary Key | Unique round identifier |
| `round_number` | Integer | Not Null | Sequential round number |
| `name` | String(100) | Nullable | Round display name |
| `scheduled_start` | DateTime(TZ) | Nullable | Planned start time |
| `scheduled_end` | DateTime(TZ) | Nullable | Planned end time |
| `actual_start` | DateTime(TZ) | Nullable | Actual start time |
| `actual_end` | DateTime(TZ) | Nullable | Actual end time |
| `duration_minutes` | Integer | Default: 5 | Round duration |
| `break_after_minutes` | Integer | Default: 2 | Break duration |
| `status` | RoundStatus | Default: PENDING | Round status |
| `is_break_active` | Boolean | Default: False | Break status |
| `auto_advance` | Boolean | Default: True | Automatic progression |
| `announcements` | String(1000) | Nullable | Round announcements |
| `notes` | String(500) | Nullable | Administrative notes |
| `created_at` | DateTime(TZ) | Auto-generated | Creation timestamp |
| `updated_at` | DateTime(TZ) | Auto-updated | Update timestamp |
| `event_id` | UUID | Foreign Key | Reference to Event |

#### Enums

**RoundStatus**:
- `PENDING`: Waiting to start
- `ACTIVE`: Currently running
- `BREAK`: Break period
- `COMPLETED`: Round finished
- `CANCELLED`: Round cancelled

#### Relationships
- **event**: Many-to-One → `Event`
- **matches**: One-to-Many → `Match` (ordered by table_number)

#### Properties
- `display_name`: User-friendly round name
- `is_active`: Check if round is running
- `is_completed`: Check if round is finished
- `total_matches`: Count of matches in round
- `completed_matches`: Count of finished matches
- `completion_percentage`: Round progress percentage

#### Methods
- `start_round()`: Begin the round
- `end_round()`: Complete the round
- `start_break()`: Begin break period
- `end_break()`: End break period
- `get_remaining_time()`: Time left in round
- `get_elapsed_time()`: Time since round started

---

### 7. Match Model

**Table**: `match`  
**Purpose**: Track pairings and responses between attendees

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | Primary Key | Unique match identifier |
| `table_number` | Integer | Not Null | Physical table assignment |
| `attendee1_response` | MatchResponse | Default: NO_RESPONSE | First attendee's response |
| `attendee2_response` | MatchResponse | Default: NO_RESPONSE | Second attendee's response |
| `attendee1_response_time` | DateTime(TZ) | Nullable | Response timestamp |
| `attendee2_response_time` | DateTime(TZ) | Nullable | Response timestamp |
| `is_completed` | Boolean | Default: False | Both responses received |
| `completed_at` | DateTime(TZ) | Nullable | Completion timestamp |
| `attendee1_notes` | Text | Nullable | Private notes |
| `attendee2_notes` | Text | Nullable | Private notes |
| `attendee1_rating` | Integer | Nullable | Rating (1-5) |
| `attendee2_rating` | Integer | Nullable | Rating (1-5) |
| `contact_exchanged` | Boolean | Default: False | Contact sharing |
| `admin_notes` | Text | Nullable | Administrative notes |
| `is_flagged` | Boolean | Default: False | Flagged for review |
| `flag_reason` | String(500) | Nullable | Flag explanation |
| `created_at` | DateTime(TZ) | Auto-generated | Creation timestamp |
| `updated_at` | DateTime(TZ) | Auto-updated | Update timestamp |
| `event_id` | UUID | Foreign Key | Reference to Event |
| `round_id` | UUID | Foreign Key | Reference to Round |
| `attendee1_id` | UUID | Foreign Key | First attendee |
| `attendee2_id` | UUID | Foreign Key | Second attendee |

#### Enums

**MatchResponse**:
- `YES`: Interested in further contact
- `NO`: Not interested
- `MAYBE`: Uncertain/conditional interest
- `NO_RESPONSE`: No response provided

#### Relationships
- **event**: Many-to-One → `Event`
- **round**: Many-to-One → `Round`
- **attendee1**: Many-to-One → `Attendee`
- **attendee2**: Many-to-One → `Attendee`

#### Properties
- `is_mutual_match`: Both attendees said YES
- `is_mutual_maybe`: Both attendees said MAYBE
- `has_mutual_interest`: Any positive mutual interest
- `both_responded`: Both attendees provided responses
- `response_completion_percentage`: Response progress

#### Methods
- `set_attendee_response()`: Record attendee response
- `get_attendee_response()`: Retrieve attendee response
- `get_other_attendee_id()`: Get pairing partner ID
- `flag_match()`: Flag for administrative review
- `unflag_match()`: Remove flag

#### Indexes
- `event_id + round_id + table_number` (Unique composite)
- `attendee1_id`
- `attendee2_id`

---

### 8. QRLogin Model

**Table**: `qr_login`  
**Purpose**: Secure QR code-based authentication system

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | Primary Key | Unique QR login identifier |
| `token` | String(100) | Unique, Not Null | QR access token |
| `token_hash` | String(128) | Not Null | Hashed token for security |
| `expires_at` | DateTime(TZ) | Not Null | Token expiration |
| `is_active` | Boolean | Default: True | Token active status |
| `used_at` | DateTime(TZ) | Nullable | Last usage timestamp |
| `usage_count` | Integer | Default: 0 | Usage counter |
| `max_uses` | Integer | Default: 1 | Maximum allowed uses |
| `ip_address` | String(45) | Nullable | Client IP address |
| `user_agent` | String(500) | Nullable | Client user agent |
| `generated_by_ip` | String(45) | Nullable | Generation IP |
| `qr_code_url` | String(500) | Nullable | QR code access URL |
| `access_granted` | Boolean | Default: False | Access status |
| `is_revoked` | Boolean | Default: False | Revocation status |
| `revoked_at` | DateTime(TZ) | Nullable | Revocation timestamp |
| `revoked_reason` | String(200) | Nullable | Revocation explanation |
| `session_id` | String(100) | Nullable | Session identifier |
| `device_fingerprint` | String(100) | Nullable | Device identification |
| `created_at` | DateTime(TZ) | Auto-generated | Creation timestamp |
| `updated_at` | DateTime(TZ) | Auto-updated | Update timestamp |
| `user_id` | UUID | Nullable FK | Reference to User |
| `event_id` | UUID | Foreign Key | Reference to Event |
| `attendee_id` | UUID | Nullable FK | Reference to Attendee |

#### Relationships
- **user**: Many-to-One → `User` (nullable)
- **event**: Many-to-One → `Event`
- **attendee**: Many-to-One → `Attendee` (nullable)

#### Properties
- `is_expired`: Check token expiration
- `is_valid`: Comprehensive validity check
- `time_until_expiry`: Remaining validity time
- `has_remaining_uses`: Usage limit check

#### Methods
- `generate_token()`: Create secure random token
- `hash_token()`: Hash token for storage
- `verify_token()`: Validate provided token
- `use_token()`: Mark token as used
- `revoke_token()`: Invalidate token
- `extend_expiry()`: Extend expiration time
- `create_for_attendee()`: Factory method for attendee tokens
- `get_qr_url()`: Generate QR code URL

#### Indexes
- `token` (Unique)
- `event_id + attendee_id`
- `expires_at`

---

## Relationships Overview

### Primary Relationships

```
User (1) ←→ (∞) OAuthAccount
User (1) ←→ (∞) Event [as organizer]
User (1) ←→ (∞) Attendee
User (1) ←→ (∞) QRLogin

Event (1) ←→ (∞) Attendee
Event (1) ←→ (∞) Round
Event (1) ←→ (∞) Match
Event (1) ←→ (∞) QRLogin

Round (1) ←→ (∞) Match

Attendee (1) ←→ (∞) Match [as attendee1]
Attendee (1) ←→ (∞) Match [as attendee2]
Attendee (1) ←→ (∞) AttendeePreference
```

### Cascade Behaviors

- **User deletion**: Cascades to all related records
- **Event deletion**: Cascades to attendees, rounds, matches, QR logins
- **Attendee deletion**: Cascades to matches and preferences
- **Round deletion**: Cascades to matches

---

## Security Features

### Authentication
- **OAuth2 Integration**: Multi-provider support via FastAPI-Users
- **Password Hashing**: Secure bcrypt hashing
- **Email Verification**: Built-in verification system
- **Role-Based Access**: Organizer and attendee roles

### QR Code Security
- **Token Hashing**: SHA-256 hashed tokens
- **Expiration**: Time-limited access
- **Usage Limits**: Configurable use counts
- **IP Tracking**: Audit trail maintenance
- **Revocation**: Immediate token invalidation

### Data Protection
- **UUID Primary Keys**: Non-sequential identifiers
- **Soft Deletion**: Audit trail preservation
- **Timestamp Tracking**: Comprehensive audit logs
- **Device Fingerprinting**: Enhanced security monitoring

---

## Performance Considerations

### Indexing Strategy
- **Primary Keys**: UUID with B-tree indexes
- **Foreign Keys**: All foreign key relationships indexed
- **Unique Constraints**: Email, QR tokens, composite keys
- **Query Optimization**: Category-based and status-based indexes

### Scalability Features
- **Async Support**: Full async/await compatibility
- **Connection Pooling**: Efficient database connections
- **Lazy Loading**: Optimized relationship loading
- **Batch Operations**: Bulk insert/update support

---

## Migration Strategy

### Database Versioning
- **Alembic Integration**: Automated schema migrations
- **Version Control**: Schema change tracking
- **Rollback Support**: Safe migration reversals
- **Data Preservation**: Zero data loss migrations

### Environment Management
- **Development**: SQLite with full debugging
- **Testing**: Isolated test database
- **Production**: PostgreSQL with optimizations

---

## Future Enhancements

### Planned Features
- **Photo Management**: Profile and event photos
- **Messaging System**: In-app communication
- **Analytics**: Advanced matching statistics
- **Integration APIs**: Third-party service connections
- **Mobile App Support**: Enhanced mobile schemas

### Performance Optimizations
- **Caching Layer**: Redis integration
- **Read Replicas**: Query performance improvement
- **Partitioning**: Large dataset optimization
- **Archive System**: Historical data management

---

This comprehensive schema provides a robust foundation for the Speed Dating Application, supporting all core features while maintaining security, performance, and scalability requirements.