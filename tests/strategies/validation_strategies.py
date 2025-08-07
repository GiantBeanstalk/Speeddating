"""
Hypothesis strategies for validation testing.

Provides strategies for testing input validation, edge cases,
and security-related data constraints.
"""

from datetime import UTC, datetime, timedelta
from hypothesis import strategies as st


# Email validation strategies
valid_email_strategy = st.from_regex(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    fullmatch=True
).filter(lambda x: len(x) <= 100)

invalid_email_strategy = st.one_of(
    st.just(""),  # Empty
    st.just("notanemail"),  # No @
    st.just("@domain.com"),  # No local part
    st.just("user@"),  # No domain
    st.just("user@domain"),  # No TLD
    st.just("user name@domain.com"),  # Space in local part
    st.just("user@domain .com"),  # Space in domain
    st.text(min_size=101, max_size=200),  # Too long
    st.from_regex(r".*@.*@.*"),  # Multiple @
)

# Phone number strategies
valid_uk_phone_strategy = st.one_of(
    st.from_regex(r"^\+44[1-9]\d{9,10}$"),  # International format
    st.from_regex(r"^0[1-9]\d{9,10}$"),     # National format
)

invalid_phone_strategy = st.one_of(
    st.just(""),  # Empty
    st.just("123"),  # Too short
    st.just("01234567890123456"),  # Too long
    st.just("00123456789"),  # Invalid prefix
    st.just("+44012345678"),  # Invalid after +44
    st.just("phone number"),  # Not numeric
    st.just("+1234567890"),  # Wrong country code
)

# UUID strategies  
valid_uuid_strategy = st.uuids().map(str)

invalid_uuid_strategy = st.one_of(
    st.just(""),  # Empty
    st.just("not-a-uuid"),  # Invalid format
    st.just("12345678"),  # Too short
    st.just("12345678-1234-1234-1234-12345678901234567890"),  # Too long
    st.just("12345678-1234-1234-1234-123456789012"),  # Almost correct
    st.text(min_size=1, max_size=50).filter(lambda x: "-" not in x),  # No hyphens
)

# Password strategies
weak_password_strategy = st.one_of(
    st.just(""),  # Empty
    st.just("123"),  # Too short
    st.just("password"),  # Common password
    st.just("12345678"),  # Only numbers
    st.just("abcdefgh"),  # Only letters
    st.text(max_size=7),  # Less than 8 characters
    st.text(min_size=129),  # More than 128 characters
)

strong_password_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\"'\\`"
    ),
    min_size=8,
    max_size=128
).filter(lambda x: any(c.isdigit() for c in x) and any(c.isalpha() for c in x))

# Bio validation strategies
valid_bio_strategy = st.text(
    min_size=10,
    max_size=1000,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        max_codepoint=127
    )
).filter(lambda x: x.strip() and len(x.strip()) >= 10)

invalid_bio_strategy = st.one_of(
    st.just(""),  # Empty
    st.text(max_size=9),  # Too short
    st.text(min_size=1001),  # Too long
    st.just("   "),  # Only whitespace
    st.just("<script>alert('xss')</script>"),  # XSS attempt
    st.just("SELECT * FROM users"),  # SQL injection attempt
)

# Age strategies
valid_age_strategy = st.integers(min_value=18, max_value=100)

invalid_age_strategy = st.one_of(
    st.integers(max_value=17),  # Too young
    st.integers(min_value=101),  # Too old
    st.integers(max_value=0),  # Negative
)

# Date/time validation strategies
valid_future_datetime_strategy = st.datetimes(
    min_value=datetime.now(UTC) + timedelta(minutes=5),
    max_value=datetime.now(UTC) + timedelta(days=365),
    timezones=st.just(UTC)
)

invalid_future_datetime_strategy = st.one_of(
    # Past dates
    st.datetimes(
        min_value=datetime.now(UTC) - timedelta(days=365),
        max_value=datetime.now(UTC) - timedelta(minutes=1),
        timezones=st.just(UTC)
    ),
    # Too far in future
    st.datetimes(
        min_value=datetime.now(UTC) + timedelta(days=366),
        max_value=datetime.now(UTC) + timedelta(days=1000),
        timezones=st.just(UTC)
    )
)

# Security-focused strategies for testing input sanitization
xss_payload_strategy = st.sampled_from([
    "<script>alert('XSS')</script>",
    "javascript:alert('XSS')",
    "<img src=x onerror=alert('XSS')>",
    "';alert('XSS');//",
    "<iframe src='javascript:alert(`XSS`)'></iframe>",
    "<<SCRIPT>alert('XSS');//<</SCRIPT>",
    "\"><script>alert('XSS')</script>",
])

sql_injection_strategy = st.sampled_from([
    "'; DROP TABLE users; --",
    "1' OR '1'='1",
    "admin'--",
    "' UNION SELECT * FROM users --",
    "1'; INSERT INTO users (email) VALUES ('hacker@evil.com'); --",
    "' OR 1=1 #",
    "1' AND (SELECT COUNT(*) FROM users) > 0 --",
])

path_traversal_strategy = st.sampled_from([
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32\\config\\sam",
    "./../config.ini",
    "file://../../sensitive.txt",
    "%2e%2e/%2e%2e/%2e%2e/etc/passwd",
])

# Large input strategies for testing limits
large_text_strategy = st.text(
    min_size=1000,
    max_size=5000,
    alphabet=st.characters(whitelist_categories=("L", "N"))
)

# Boundary value strategies
boundary_values_strategy = st.sampled_from([
    -1, 0, 1,  # Around zero
    17, 18, 19,  # Around minimum age
    99, 100, 101,  # Around maximum age  
    127, 128, 129,  # Around ASCII limit
    255, 256, 257,  # Around byte limit
    65535, 65536, 65537,  # Around 16-bit limit
])

# Special character strategies for testing encoding/decoding
special_characters_strategy = st.text(
    alphabet=st.characters(
        categories=("P", "S", "Z"),
        blacklist_categories=("C",)  # Avoid control characters
    ),
    min_size=1,
    max_size=50
)

unicode_strategy = st.text(
    alphabet=st.characters(
        min_codepoint=128,
        max_codepoint=1000,
        blacklist_categories=("C",)
    ),
    min_size=1,
    max_size=20
)

# Combined validation strategy for comprehensive testing
@st.composite
def malicious_input_strategy(draw):
    """Generate potentially malicious input for security testing."""
    return draw(st.one_of(
        xss_payload_strategy,
        sql_injection_strategy, 
        path_traversal_strategy,
        large_text_strategy,
        special_characters_strategy,
        unicode_strategy
    ))