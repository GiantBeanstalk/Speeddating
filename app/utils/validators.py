"""
Validation utilities for contact information and other fields.
"""

import re

from pydantic import field_validator


def validate_uk_phone_number(phone: str) -> bool:
    """
    Validate UK phone numbers.

    Accepts formats like:
    - +44 7123 456789
    - 07123 456789
    - +447123456789
    - 07123456789
    - +44 (0)7123 456789
    - 020 7123 4567 (London landline)
    - +44 20 7123 4567
    """
    if not phone:
        return False

    # Remove all spaces, hyphens, and parentheses
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)

    # UK mobile patterns
    uk_mobile_patterns = [
        r"^\+447[0-9]{9}$",  # +447xxxxxxxxx
        r"^07[0-9]{9}$",  # 07xxxxxxxxx
    ]

    # UK landline patterns (major cities)
    uk_landline_patterns = [
        r"^\+4420[0-9]{8}$",  # +44 20 xxxxxxxx (London)
        r"^020[0-9]{8}$",  # 020 xxxxxxxx (London)
        r"^\+44121[0-9]{7}$",  # +44 121 xxxxxxx (Birmingham)
        r"^0121[0-9]{7}$",  # 0121 xxxxxxx (Birmingham)
        r"^\+44161[0-9]{7}$",  # +44 161 xxxxxxx (Manchester)
        r"^0161[0-9]{7}$",  # 0161 xxxxxxx (Manchester)
        r"^\+44113[0-9]{7}$",  # +44 113 xxxxxxx (Leeds)
        r"^0113[0-9]{7}$",  # 0113 xxxxxxx (Leeds)
        r"^\+44117[0-9]{7}$",  # +44 117 xxxxxxx (Bristol)
        r"^0117[0-9]{7}$",  # 0117 xxxxxxx (Bristol)
        r"^\+441[0-9]{9}$",  # +44 1xxx xxxxxx (other areas)
        r"^01[0-9]{9}$",  # 01xxx xxxxxx (other areas)
    ]

    # Check against all patterns
    all_patterns = uk_mobile_patterns + uk_landline_patterns

    for pattern in all_patterns:
        if re.match(pattern, cleaned):
            return True

    return False


def validate_email(email: str) -> bool:
    """
    Validate email addresses using a comprehensive regex.
    """
    if not email:
        return False

    # Email regex pattern (RFC 5322 compliant)
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    return re.match(email_pattern, email) is not None


def validate_fetlife_username(username: str) -> bool:
    """
    Validate FetLife usernames.

    FetLife usernames are typically:
    - 3-20 characters long
    - Letters, numbers, underscores, hyphens
    - Cannot start or end with underscore or hyphen
    """
    if not username:
        return False

    # Remove @ if user includes it
    if username.startswith("@"):
        username = username[1:]

    # FetLife username pattern
    fetlife_pattern = r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,18}[a-zA-Z0-9]$"

    # Allow single character usernames
    if len(username) == 1:
        return re.match(r"^[a-zA-Z0-9]$", username) is not None

    return re.match(fetlife_pattern, username) is not None


def format_uk_phone_number(phone: str) -> str:
    """
    Format UK phone number to a standard format.
    """
    if not phone:
        return phone

    # Remove all non-digit characters except +
    cleaned = re.sub(r"[^\d+]", "", phone)

    # Convert to international format
    if cleaned.startswith("0"):
        cleaned = "+44" + cleaned[1:]
    elif not cleaned.startswith("+44"):
        # Assume it's already without country code
        cleaned = "+44" + cleaned

    # Format mobile numbers
    if cleaned.startswith("+447"):
        return f"{cleaned[:3]} {cleaned[3:7]} {cleaned[7:]}"

    # Format London landlines
    elif cleaned.startswith("+4420"):
        return f"{cleaned[:5]} {cleaned[5:9]} {cleaned[9:]}"

    # Format other landlines
    elif cleaned.startswith("+441"):
        if len(cleaned) == 13:  # +44 1xxx xxxxxx
            return f"{cleaned[:6]} {cleaned[6:]}"
        elif len(cleaned) == 14:  # +44 1xxxx xxxxx
            return f"{cleaned[:7]} {cleaned[7:]}"

    return cleaned


class ContactValidationMixin:
    """Mixin class for contact validation in Pydantic models."""

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email(cls, v):
        if v and not validate_email(v):
            raise ValueError("Invalid email address format")
        return v

    @field_validator("contact_phone")
    @classmethod
    def validate_contact_phone(cls, v):
        if v and not validate_uk_phone_number(v):
            raise ValueError("Invalid UK phone number format")
        return format_uk_phone_number(v) if v else v

    @field_validator("fetlife_username")
    @classmethod
    def validate_fetlife_username(cls, v):
        if v and not validate_fetlife_username(v):
            raise ValueError("Invalid FetLife username format")
        return v.lstrip("@") if v else v  # Remove @ if present
