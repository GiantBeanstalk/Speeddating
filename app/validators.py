"""
Comprehensive validation utilities for the Speed Dating application.

Provides centralized validation functions for common data types,
business rules, and input sanitization.
"""

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from app.exceptions import ValidationError


class Validators:
    """Collection of validation functions for common data types."""

    # Regular expressions for validation
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    UK_PHONE_PATTERN = re.compile(r"^(\+44|0)[1-9]\d{8,9}$")
    FETLIFE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
    UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )

    @staticmethod
    def validate_email(email: str, field_name: str = "email") -> str:
        """Validate email address format."""
        if not email:
            raise ValidationError(f"{field_name} is required", field=field_name)

        email = email.strip().lower()

        if len(email) > 254:
            raise ValidationError(
                f"{field_name} is too long", field=field_name, value=email
            )

        if not Validators.EMAIL_PATTERN.match(email):
            raise ValidationError(
                f"Invalid {field_name} format", field=field_name, value=email
            )

        return email

    @staticmethod
    def validate_uk_phone(phone: str, field_name: str = "phone") -> str:
        """Validate UK phone number format."""
        if not phone:
            raise ValidationError(f"{field_name} is required", field=field_name)

        # Remove spaces and hyphens
        phone_cleaned = re.sub(r"[\s-]", "", phone.strip())

        if not Validators.UK_PHONE_PATTERN.match(phone_cleaned):
            raise ValidationError(
                f"Invalid UK {field_name} format. Use +44XXXXXXXXXX or 0XXXXXXXXXXX",
                field=field_name,
                value=phone,
            )

        return phone_cleaned

    @staticmethod
    def validate_fetlife_username(
        username: str, field_name: str = "fetlife_username"
    ) -> str:
        """Validate FetLife username format."""
        if not username:
            return username  # FetLife username is optional

        username = username.strip()

        if len(username) < 3:
            raise ValidationError(
                f"{field_name} must be at least 3 characters",
                field=field_name,
                value=username,
            )

        if len(username) > 50:
            raise ValidationError(
                f"{field_name} must be less than 50 characters",
                field=field_name,
                value=username,
            )

        if not Validators.FETLIFE_PATTERN.match(username):
            raise ValidationError(
                f"Invalid {field_name} format. Only letters, numbers, hyphens, and underscores allowed",
                field=field_name,
                value=username,
            )

        return username

    @staticmethod
    def validate_uuid(value: str | uuid.UUID, field_name: str = "id") -> uuid.UUID:
        """Validate UUID format."""
        if isinstance(value, uuid.UUID):
            return value

        if not value:
            raise ValidationError(f"{field_name} is required", field=field_name)

        value_str = str(value).strip()

        if not Validators.UUID_PATTERN.match(value_str):
            raise ValidationError(
                f"Invalid {field_name} format", field=field_name, value=value_str
            )

        try:
            return uuid.UUID(value_str)
        except ValueError as e:
            raise ValidationError(
                f"Invalid {field_name} format", field=field_name, value=value_str
            ) from e

    @staticmethod
    def validate_string_length(
        value: str,
        min_length: int = 0,
        max_length: int = 1000,
        field_name: str = "field",
    ) -> str:
        """Validate string length constraints."""
        if not value and min_length > 0:
            raise ValidationError(f"{field_name} is required", field=field_name)

        if value is None:
            value = ""

        value = str(value).strip()

        if len(value) < min_length:
            raise ValidationError(
                f"{field_name} must be at least {min_length} characters",
                field=field_name,
                value=value,
            )

        if len(value) > max_length:
            raise ValidationError(
                f"{field_name} must be less than {max_length} characters",
                field=field_name,
                value=value,
            )

        return value

    @staticmethod
    def validate_integer_range(
        value: int,
        min_value: int | None = None,
        max_value: int | None = None,
        field_name: str = "field",
    ) -> int:
        """Validate integer within range."""
        if not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError) as e:
                raise ValidationError(
                    f"{field_name} must be an integer", field=field_name, value=value
                ) from e

        if min_value is not None and value < min_value:
            raise ValidationError(
                f"{field_name} must be at least {min_value}",
                field=field_name,
                value=value,
            )

        if max_value is not None and value > max_value:
            raise ValidationError(
                f"{field_name} must be at most {max_value}",
                field=field_name,
                value=value,
            )

        return value

    @staticmethod
    def validate_datetime(
        value: str | datetime, field_name: str = "datetime"
    ) -> datetime:
        """Validate datetime format and convert to timezone-aware datetime."""
        if isinstance(value, datetime):
            # Ensure timezone aware
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            return value

        if not value:
            raise ValidationError(f"{field_name} is required", field=field_name)

        try:
            # Try parsing ISO format first
            parsed_dt = datetime.fromisoformat(str(value))
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=UTC)
            return parsed_dt
        except ValueError as e:
            raise ValidationError(
                f"Invalid {field_name} format", field=field_name, value=str(value)
            ) from e

    @staticmethod
    def validate_future_datetime(
        value: str | datetime, field_name: str = "datetime", min_future_minutes: int = 5
    ) -> datetime:
        """Validate that datetime is in the future."""
        dt_value = Validators.validate_datetime(value, field_name)

        min_time = datetime.now(UTC) + timedelta(minutes=min_future_minutes)

        if dt_value <= min_time:
            raise ValidationError(
                f"{field_name} must be at least {min_future_minutes} minutes in the future",
                field=field_name,
                value=dt_value.isoformat(),
            )

        return dt_value

    @staticmethod
    def validate_url(value: str, field_name: str = "url") -> str:
        """Validate URL format."""
        if not value:
            raise ValidationError(f"{field_name} is required", field=field_name)

        value = value.strip()

        try:
            result = urlparse(value)
            if not all([result.scheme, result.netloc]):
                raise ValidationError(
                    f"Invalid {field_name} format", field=field_name, value=value
                )

            if result.scheme not in ["http", "https"]:
                raise ValidationError(
                    f"{field_name} must use HTTP or HTTPS protocol",
                    field=field_name,
                    value=value,
                )

        except Exception as e:
            raise ValidationError(
                f"Invalid {field_name} format", field=field_name, value=value
            ) from e

        return value

    @staticmethod
    def sanitize_html_input(value: str, field_name: str = "field") -> str:
        """Sanitize HTML input to prevent XSS attacks."""
        if not value:
            return ""

        # Basic HTML sanitization - remove script tags and attributes
        import html

        # HTML encode the input
        sanitized = html.escape(str(value).strip())

        # Remove any remaining script-like content
        dangerous_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>.*?</iframe>",
            r"<object[^>]*>.*?</object>",
            r"<embed[^>]*>.*?</embed>",
        ]

        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE | re.DOTALL)

        return sanitized

    @staticmethod
    def validate_choice(
        value: Any, choices: list[Any], field_name: str = "field"
    ) -> Any:
        """Validate that value is one of the allowed choices."""
        if value not in choices:
            raise ValidationError(
                f"{field_name} must be one of: {', '.join(str(c) for c in choices)}",
                field=field_name,
                value=str(value),
            )

        return value


class BusinessRuleValidators:
    """Validators for business logic rules specific to speed dating."""

    @staticmethod
    def validate_event_capacity(
        current_attendees: int, max_capacity: int, additional_attendees: int = 1
    ):
        """Validate event capacity constraints."""
        if current_attendees + additional_attendees > max_capacity:
            raise ValidationError(
                f"Event capacity exceeded. Current: {current_attendees}, "
                f"Max: {max_capacity}, Trying to add: {additional_attendees}",
                field="capacity",
                details={
                    "current_attendees": current_attendees,
                    "max_capacity": max_capacity,
                    "additional_attendees": additional_attendees,
                },
            )

    @staticmethod
    def validate_event_timing(
        event_date: datetime, registration_deadline: datetime | None = None
    ):
        """Validate event timing constraints."""
        now = datetime.now(UTC)

        # Event must be in the future
        if event_date <= now:
            raise ValidationError(
                "Event date must be in the future",
                field="event_date",
                value=event_date.isoformat(),
            )

        # Registration deadline must be before event date
        if registration_deadline and registration_deadline >= event_date:
            raise ValidationError(
                "Registration deadline must be before event date",
                field="registration_deadline",
                value=registration_deadline.isoformat(),
            )

        # Event should not be too far in the future (1 year)
        max_future_date = now + timedelta(days=365)
        if event_date > max_future_date:
            raise ValidationError(
                "Event date cannot be more than 1 year in the future",
                field="event_date",
                value=event_date.isoformat(),
            )

    @staticmethod
    def validate_round_duration(duration_minutes: int, break_minutes: int = 0):
        """Validate round duration constraints."""
        Validators.validate_integer_range(
            duration_minutes, min_value=1, max_value=60, field_name="duration_minutes"
        )

        Validators.validate_integer_range(
            break_minutes, min_value=0, max_value=30, field_name="break_minutes"
        )

    @staticmethod
    def validate_attendee_categories(attendees: list[dict[str, Any]]):
        """Validate that attendees can be matched (multiple categories)."""
        categories = set()
        for attendee in attendees:
            if attendee.get("registration_confirmed"):
                categories.add(attendee.get("category"))

        if len(categories) < 2:
            raise ValidationError(
                "Need attendees from at least 2 categories to create matches",
                field="attendees",
                details={"categories": list(categories)},
            )

    @staticmethod
    def validate_password_strength(password: str) -> str:
        """Validate password strength requirements."""
        if len(password) < 8:
            raise ValidationError(
                "Password must be at least 8 characters long", field="password"
            )

        if len(password) > 128:
            raise ValidationError(
                "Password cannot be longer than 128 characters", field="password"
            )

        # Check for at least one uppercase, lowercase, digit, and special char
        requirements = [
            (r"[A-Z]", "uppercase letter"),
            (r"[a-z]", "lowercase letter"),
            (r"\d", "number"),
            (r'[!@#$%^&*(),.?":{}|<>]', "special character"),
        ]

        missing = []
        for pattern, requirement in requirements:
            if not re.search(pattern, password):
                missing.append(requirement)

        if missing:
            raise ValidationError(
                f"Password must contain at least one: {', '.join(missing)}",
                field="password",
            )

        return password


def validate_request_data(
    data: dict[str, Any], validation_rules: dict[str, Any]
) -> dict[str, Any]:
    """
    Validate request data against a set of validation rules.

    Args:
        data: The data to validate
        validation_rules: Dictionary of field_name -> validation_function mappings

    Returns:
        Validated and sanitized data
    """
    validated_data = {}
    errors = []

    for field_name, validator in validation_rules.items():
        try:
            if field_name in data:
                validated_data[field_name] = validator(data[field_name])
            elif hasattr(validator, "__defaults__") and validator.__defaults__:
                # Use default value if available
                validated_data[field_name] = validator()
        except ValidationError as e:
            errors.append(e)

    if errors:
        # Combine all validation errors
        combined_details = {}
        for error in errors:
            combined_details.update(error.details)

        raise ValidationError(
            f"Validation failed for {len(errors)} field(s)", details=combined_details
        )

    return validated_data
