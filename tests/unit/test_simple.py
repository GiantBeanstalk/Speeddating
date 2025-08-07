"""
Simple unit tests to verify testing infrastructure works.
"""

import pytest
from hypothesis import given, strategies as st

from tests.fixtures.faker_providers import setup_faker_providers


@pytest.mark.unit
def test_faker_providers():
    """Test that our custom Faker providers work."""
    fake = setup_faker_providers()
    
    # Test UK phone number generation
    phone = fake.uk_phone_number()
    assert isinstance(phone, str)
    assert len(phone) >= 11
    # Check it's a valid UK format (starts with 0 or +44)
    assert phone.startswith("0") or phone.startswith("+44")
    
    # Test FetLife username generation
    username = fake.fetlife_username()
    assert isinstance(username, str)
    assert len(username) > 0
    
    # Test event name generation
    event_name = fake.event_name()
    assert isinstance(event_name, str)
    assert len(event_name) > 0
    
    # Test venue generation
    venue = fake.venue_name()
    assert isinstance(venue, str)
    assert len(venue) > 0


@pytest.mark.unit
@pytest.mark.hypothesis
class TestHypothesisStrategies:
    """Test that our Hypothesis strategies work."""
    
    @given(email=st.emails())
    def test_email_strategy(self, email):
        """Test basic email generation."""
        assert "@" in email
        assert "." in email
        assert len(email) > 3
    
    @given(age=st.integers(min_value=18, max_value=100))
    def test_age_strategy(self, age):
        """Test age generation."""
        assert 18 <= age <= 100
        assert isinstance(age, int)
    
    @given(text=st.text(min_size=1, max_size=100))
    def test_text_strategy(self, text):
        """Test text generation."""
        assert len(text) >= 1
        assert len(text) <= 100


@pytest.mark.unit
def test_pytest_configuration():
    """Test that pytest is configured correctly."""
    # Test basic assertions work
    assert True
    assert 1 + 1 == 2
    assert "test" in "testing"
    
    # Test we can import our modules
    from tests.fixtures.faker_providers import fake
    assert hasattr(fake, 'uk_phone_number')
    assert hasattr(fake, 'event_name')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])