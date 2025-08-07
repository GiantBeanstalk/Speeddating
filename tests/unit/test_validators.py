"""
Unit tests for validation system using Hypothesis property-based testing.

Tests input validation, sanitization, and security measures
with realistic and malicious data generation.
"""

import pytest
import uuid
from datetime import UTC, datetime, timedelta
from hypothesis import given, assume, strategies as st

from app.validators import Validators
from app.exceptions import ValidationError
from tests.strategies.validation_strategies import (
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


@pytest.mark.unit
@pytest.mark.hypothesis
class TestEmailValidation:
    """Test email validation with property-based testing."""
    
    @given(email=valid_email_strategy)
    def test_valid_email_acceptance(self, email):
        """Test that valid emails are accepted."""
        result = Validators.validate_email(email)
        assert result == email.lower()  # Should be normalized to lowercase
        assert "@" in result
        assert "." in result.split("@")[1]  # Domain has TLD
    
    @given(email=invalid_email_strategy)
    def test_invalid_email_rejection(self, email):
        """Test that invalid emails are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Validators.validate_email(email)
        
        assert "email" in exc_info.value.message.lower()
        assert exc_info.value.field == "email"
        assert exc_info.value.value == email
    
    @given(email=valid_email_strategy)
    def test_email_normalization(self, email):
        """Test that emails are normalized consistently."""
        result1 = Validators.validate_email(email)
        result2 = Validators.validate_email(email.upper())
        result3 = Validators.validate_email(email.lower())
        
        assert result1 == result2 == result3
        assert result1.islower()
    
    @given(malicious_input=malicious_input_strategy())
    def test_email_security_filtering(self, malicious_input):
        """Test that malicious input in email fields is rejected."""
        with pytest.raises(ValidationError):
            Validators.validate_email(malicious_input)


@pytest.mark.unit
@pytest.mark.hypothesis
class TestPhoneValidation:
    """Test UK phone number validation."""
    
    @given(phone=valid_uk_phone_strategy)
    def test_valid_phone_acceptance(self, phone):
        """Test that valid UK phone numbers are accepted."""
        result = Validators.validate_uk_phone(phone)
        assert result is not None
        assert len(result) >= 11  # UK numbers are at least 11 digits
        assert result.startswith(("+44", "0"))
    
    @given(phone=invalid_phone_strategy)
    def test_invalid_phone_rejection(self, phone):
        """Test that invalid phone numbers are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Validators.validate_uk_phone(phone)
        
        assert "phone" in exc_info.value.message.lower()
        assert exc_info.value.field == "phone"
    
    @given(
        phone=st.from_regex(r"^\+44[1-9]\d{9,10}$")
    )
    def test_international_format_normalization(self, phone):
        """Test international format phone numbers."""
        result = Validators.validate_uk_phone(phone)
        assert result.startswith("+44")
        assert not result.startswith("+440")  # No leading zero after +44
    
    @given(
        phone=st.from_regex(r"^0[1-9]\d{9,10}$")
    )
    def test_national_format_normalization(self, phone):
        """Test national format phone numbers."""
        result = Validators.validate_uk_phone(phone)
        assert result.startswith("0")


@pytest.mark.unit
@pytest.mark.hypothesis
class TestUUIDValidation:
    """Test UUID validation."""
    
    @given(uuid_str=valid_uuid_strategy)
    def test_valid_uuid_acceptance(self, uuid_str):
        """Test that valid UUIDs are accepted."""
        result = Validators.validate_uuid(uuid_str)
        assert isinstance(result, uuid.UUID)
        assert str(result) == str(uuid_str).lower()  # Normalized format
    
    @given(uuid_str=invalid_uuid_strategy)
    def test_invalid_uuid_rejection(self, uuid_str):
        """Test that invalid UUIDs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Validators.validate_uuid(uuid_str)
        
        assert "uuid" in exc_info.value.message.lower() or "format" in exc_info.value.message.lower()
    
    @given(uuid_obj=st.uuids())
    def test_uuid_object_handling(self, uuid_obj):
        """Test that UUID objects are handled correctly."""
        result = Validators.validate_uuid(uuid_obj)
        assert isinstance(result, uuid.UUID)
        assert result == uuid_obj


@pytest.mark.unit
@pytest.mark.hypothesis  
class TestPasswordValidation:
    """Test password strength validation."""
    
    @given(password=weak_password_strategy)
    def test_weak_password_rejection(self, password):
        """Test that weak passwords are rejected."""
        assume(len(password) < 8 or password.isdigit() or password.isalpha() or not password.strip())
        
        with pytest.raises(ValidationError) as exc_info:
            Validators.validate_password_strength(password)
        
        assert "password" in exc_info.value.message.lower()
    
    @given(password=strong_password_strategy)
    def test_strong_password_acceptance(self, password):
        """Test that strong passwords are accepted."""
        assume(8 <= len(password) <= 128)
        assume(any(c.isdigit() for c in password))
        assume(any(c.isalpha() for c in password))
        
        result = Validators.validate_password_strength(password)
        assert result == password  # Password returned unchanged
    
    @given(password=st.text(min_size=8, max_size=20))
    def test_password_length_validation(self, password):
        """Test password length requirements."""
        if len(password) < 8:
            with pytest.raises(ValidationError):
                Validators.validate_password_strength(password)
        elif len(password) > 128:
            with pytest.raises(ValidationError):
                Validators.validate_password_strength(password)


@pytest.mark.unit
@pytest.mark.hypothesis
class TestBioValidation:
    """Test profile bio validation."""
    
    @given(bio=valid_bio_strategy)
    def test_valid_bio_acceptance(self, bio):
        """Test that valid bios are accepted."""
        assume(len(bio.strip()) >= 10)
        
        result = Validators.validate_bio(bio)
        assert len(result) >= 10
        assert result.strip() == result  # No leading/trailing whitespace
    
    @given(bio=invalid_bio_strategy)
    def test_invalid_bio_rejection(self, bio):
        """Test that invalid bios are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Validators.validate_bio(bio)
        
        assert "bio" in exc_info.value.message.lower() or "description" in exc_info.value.message.lower()
    
    @given(xss_payload=xss_payload_strategy)
    def test_bio_xss_protection(self, xss_payload):
        """Test that XSS payloads in bios are sanitized or rejected."""
        # Bio validation should either reject malicious content or sanitize it
        try:
            result = Validators.validate_bio(xss_payload)
            # If accepted, should not contain script tags or javascript
            assert "<script" not in result.lower()
            assert "javascript:" not in result.lower()
            assert "onerror=" not in result.lower()
        except ValidationError:
            # Rejection is also acceptable
            pass


@pytest.mark.unit
@pytest.mark.hypothesis
class TestAgeValidation:
    """Test age validation."""
    
    @given(age=valid_age_strategy)
    def test_valid_age_acceptance(self, age):
        """Test that valid ages are accepted."""
        result = Validators.validate_integer(age, min_value=18, max_value=100, field_name="age")
        assert result == age
        assert 18 <= result <= 100
    
    @given(age=invalid_age_strategy)
    def test_invalid_age_rejection(self, age):
        """Test that invalid ages are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Validators.validate_integer(age, min_value=18, max_value=100, field_name="age")
        
        assert "age" in exc_info.value.message.lower()


@pytest.mark.unit
@pytest.mark.hypothesis
class TestDateTimeValidation:
    """Test datetime validation."""
    
    @given(dt=valid_future_datetime_strategy)
    def test_valid_future_datetime_acceptance(self, dt):
        """Test that valid future datetimes are accepted."""
        assume(dt > datetime.now(UTC) + timedelta(minutes=1))
        
        result = Validators.validate_future_datetime(dt.isoformat())
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC
        assert result > datetime.now(UTC)
    
    @given(dt=invalid_future_datetime_strategy)
    def test_invalid_future_datetime_rejection(self, dt):
        """Test that past or invalid datetimes are rejected."""
        with pytest.raises(ValidationError):
            Validators.validate_future_datetime(dt.isoformat())
    
    @given(dt_str=st.text())
    def test_malformed_datetime_rejection(self, dt_str):
        """Test that malformed datetime strings are rejected."""
        assume(dt_str not in ["", "null", "None"])
        assume(not dt_str.isspace())
        
        # Most random strings should be invalid datetime formats
        try:
            datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            # If it's not a valid datetime format, validation should fail
            with pytest.raises(ValidationError):
                Validators.validate_future_datetime(dt_str)


@pytest.mark.unit
@pytest.mark.hypothesis
class TestInputSanitization:
    """Test input sanitization and security measures."""
    
    @given(malicious_input=xss_payload_strategy)
    def test_html_sanitization(self, malicious_input):
        """Test that HTML/XSS payloads are sanitized."""
        result = Validators.sanitize_html_input(malicious_input)
        
        # Should not contain dangerous elements
        assert "<script" not in result.lower()
        assert "javascript:" not in result.lower()
        assert "onerror=" not in result.lower()
        assert "<iframe" not in result.lower()
    
    @given(sql_payload=sql_injection_strategy)
    def test_sql_injection_protection(self, sql_payload):
        """Test protection against SQL injection attempts."""
        # Basic SQL injection patterns should be rejected or sanitized
        result = Validators.sanitize_html_input(sql_payload)
        
        # Common SQL injection patterns should be neutralized
        dangerous_patterns = ["drop table", "union select", "1'='1", "--", ";"]
        result_lower = result.lower()
        
        # The sanitizer should remove or escape dangerous SQL patterns
        # This is a basic test - real protection happens at the ORM level
        assert result != sql_payload or not any(pattern in result_lower for pattern in dangerous_patterns)
    
    @given(
        text=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "Z"),
                max_codepoint=1000
            ),
            min_size=1,
            max_size=1000
        )
    )
    def test_safe_text_preservation(self, text):
        """Test that safe text is preserved during sanitization."""
        assume(not any(dangerous in text.lower() for dangerous in ["<script", "javascript:", "<iframe"]))
        
        result = Validators.sanitize_html_input(text)
        
        # Safe text should be mostly preserved (may have whitespace normalized)
        assert len(result) > 0
        # Basic content should be similar (allowing for whitespace changes)
        assert any(word in result for word in text.split() if len(word) > 2)


@pytest.mark.unit
@pytest.mark.hypothesis
class TestValidationIntegration:
    """Test integration of multiple validation rules."""
    
    @given(
        email=valid_email_strategy,
        phone=valid_uk_phone_strategy,
        age=valid_age_strategy,
        bio=valid_bio_strategy
    )
    def test_complete_user_data_validation(self, email, phone, age, bio):
        """Test validation of complete user profile data."""
        assume(len(bio.strip()) >= 10)
        assume(18 <= age <= 100)
        
        # All validations should pass
        validated_email = Validators.validate_email(email)
        validated_phone = Validators.validate_uk_phone(phone)
        validated_age = Validators.validate_integer(age, min_value=18, max_value=100)
        validated_bio = Validators.validate_bio(bio)
        
        assert validated_email == email.lower()
        assert validated_phone is not None
        assert validated_age == age
        assert len(validated_bio.strip()) >= 10
    
    @given(data_dict=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(
            st.text(),
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans()
        ),
        min_size=1,
        max_size=10
    ))
    def test_bulk_data_validation(self, data_dict):
        """Test validation of dictionary data structures."""
        # This would test a bulk validation function if implemented
        # For now, just test that we can iterate and validate individual fields
        
        for key, value in data_dict.items():
            if isinstance(value, str) and "@" in value:
                try:
                    Validators.validate_email(value)
                except ValidationError:
                    pass  # Expected for most random strings
            
            if isinstance(value, int) and 0 <= value <= 200:
                try:
                    Validators.validate_integer(value, min_value=0, max_value=200)
                except ValidationError:
                    pass  # Some values may still be invalid
        
        # Test passes if no exceptions are raised during iteration