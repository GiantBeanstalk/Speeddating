"""
Hypothesis strategies for property-based testing.

Provides strategies for generating domain objects like users, events,
matches, and other Speed Dating application entities.
"""

from .core_strategies import (
    user_strategy,
    event_strategy, 
    attendee_strategy,
    round_strategy,
    match_strategy,
    qr_login_strategy,
)

from .validation_strategies import (
    valid_email_strategy,
    invalid_email_strategy,
    valid_uk_phone_strategy,
    invalid_phone_strategy,
    valid_uuid_strategy,
    invalid_uuid_strategy,
    weak_password_strategy,
    strong_password_strategy,
    valid_bio_strategy,
    invalid_bio_strategy,
    valid_age_strategy,
    invalid_age_strategy,
    valid_future_datetime_strategy,
    invalid_future_datetime_strategy,
    xss_payload_strategy,
    sql_injection_strategy,
    malicious_input_strategy,
)

from .api_strategies import (
    api_request_strategy,
    api_response_strategy,
    error_response_strategy,
)

__all__ = [
    "user_strategy",
    "event_strategy", 
    "attendee_strategy",
    "round_strategy",
    "match_strategy",
    "qr_login_strategy",
    "valid_email_strategy",
    "invalid_email_strategy",
    "valid_uk_phone_strategy",
    "invalid_phone_strategy", 
    "valid_uuid_strategy",
    "invalid_uuid_strategy",
    "weak_password_strategy",
    "strong_password_strategy",
    "valid_bio_strategy",
    "invalid_bio_strategy",
    "valid_age_strategy",
    "invalid_age_strategy",
    "valid_future_datetime_strategy",
    "invalid_future_datetime_strategy",
    "xss_payload_strategy",
    "sql_injection_strategy",
    "malicious_input_strategy",
    "api_request_strategy",
    "api_response_strategy",
    "error_response_strategy",
]