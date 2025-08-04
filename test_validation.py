#!/usr/bin/env python3
"""
Simple test script to validate the contact information validators.
Run this to test UK phone number, email, and FetLife username validation.
"""

from app.utils.validators import (
    validate_uk_phone_number,
    validate_email,
    validate_fetlife_username,
    format_uk_phone_number
)

def test_uk_phone_numbers():
    print("Testing UK Phone Number Validation:")
    
    valid_numbers = [
        "+44 7123 456789",
        "07123 456789", 
        "+447123456789",
        "07123456789",
        "+44 (0)7123 456789",
        "020 7123 4567",
        "+44 20 7123 4567",
        "0121 496 0000",
        "+44 121 496 0000",
        "01234 567890",
        "+44 1234 567890"
    ]
    
    invalid_numbers = [
        "123456789",  # Too short
        "07123 456789 123",  # Too long
        "+1 555 123 4567",  # US number
        "0812345678",  # Invalid UK area code
        "abcd efgh ijkl",  # Letters
        "",  # Empty
        "+44 0123 456789"  # Invalid format
    ]
    
    print("Valid numbers:")
    for number in valid_numbers:
        result = validate_uk_phone_number(number)
        formatted = format_uk_phone_number(number) if result else "N/A"
        print(f"  {number:<20} -> {result} -> {formatted}")
    
    print("\nInvalid numbers:")
    for number in invalid_numbers:
        result = validate_uk_phone_number(number)
        print(f"  {number:<20} -> {result}")


def test_email_validation():
    print("\n\nTesting Email Validation:")
    
    valid_emails = [
        "test@example.com",
        "user.name@domain.co.uk",
        "user+tag@domain.com",
        "user_name@domain-name.com",
        "123@domain.com"
    ]
    
    invalid_emails = [
        "invalid-email",
        "@domain.com",
        "user@",
        "user..name@domain.com",
        "user@domain",
        "",
        "user name@domain.com"  # Space not allowed
    ]
    
    print("Valid emails:")
    for email in valid_emails:
        result = validate_email(email)
        print(f"  {email:<30} -> {result}")
    
    print("\nInvalid emails:")
    for email in invalid_emails:
        result = validate_email(email)
        print(f"  {email:<30} -> {result}")


def test_fetlife_validation():
    print("\n\nTesting FetLife Username Validation:")
    
    valid_usernames = [
        "username",
        "user123",
        "user_name",
        "user-name",
        "a",  # Single character
        "@username",  # With @ (should be cleaned)
        "Username123",
        "user_123_name"
    ]
    
    invalid_usernames = [
        "_username",  # Can't start with underscore
        "username_",  # Can't end with underscore
        "-username",  # Can't start with hyphen
        "username-",  # Can't end with hyphen
        "",  # Empty
        "a" * 21,  # Too long
        "user@name",  # Invalid character
        "user name"  # Space not allowed
    ]
    
    print("Valid usernames:")
    for username in valid_usernames:
        result = validate_fetlife_username(username)
        cleaned = username.lstrip('@') if username else username
        print(f"  {username:<20} -> {result} -> {cleaned}")
    
    print("\nInvalid usernames:")
    for username in invalid_usernames:
        result = validate_fetlife_username(username)
        print(f"  {username:<20} -> {result}")


if __name__ == "__main__":
    test_uk_phone_numbers()
    test_email_validation()
    test_fetlife_validation()