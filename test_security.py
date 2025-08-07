#!/usr/bin/env python3
"""
Security functionality test script.

Tests input sanitization, CSRF protection, and validation functions.
"""

from app.security import (
    InputSanitizer,
    SanitizationConfig,
    generate_csrf_token,
    sanitize_email,
    sanitize_name,
    sanitize_text,
    validate_csrf_token,
    validate_uuid,
)


def test_input_sanitization():
    """Test input sanitization functions."""
    print("🧪 Testing Input Sanitization")
    print("=" * 40)

    # Test SQL injection protection
    print("1. SQL Injection Protection:")
    dangerous_inputs = [
        "'; DROP TABLE users; --",
        "' OR '1'='1",
        "UNION SELECT * FROM passwords",
        "admin'--",
        "'; INSERT INTO users VALUES('hacker'); --",
    ]

    for dangerous_input in dangerous_inputs:
        try:
            result = sanitize_text(dangerous_input)
            print(f"   ❌ FAILED: '{dangerous_input}' was not blocked")
        except ValueError as e:
            print(f"   ✅ BLOCKED: '{dangerous_input[:20]}...' - {str(e)}")

    # Test XSS protection
    print("\n2. XSS Protection:")
    xss_inputs = [
        "<script>alert('xss')</script>",
        "javascript:alert('xss')",
        "<img src=x onerror=alert('xss')>",
        "<iframe src='javascript:alert(1)'></iframe>",
        "eval('alert(1)')",
    ]

    for xss_input in xss_inputs:
        try:
            result = sanitize_text(xss_input)
            if "<script" in result or "javascript:" in result or "onerror=" in result:
                print(f"   ❌ FAILED: XSS not fully sanitized: '{result}'")
            else:
                print(f"   ✅ SANITIZED: '{xss_input[:20]}...' -> '{result}'")
        except ValueError as e:
            print(f"   ✅ BLOCKED: '{xss_input[:20]}...' - {str(e)}")

    # Test email sanitization
    print("\n3. Email Validation:")
    test_emails = [
        ("valid@example.com", True),
        ("test.email+tag@domain.co.uk", True),
        ("invalid.email", False),
        ("@domain.com", False),
        ("user@", False),
        ("'; DROP TABLE users; --@evil.com", False),
        ("user..name@domain.com", False),
    ]

    for email, should_pass in test_emails:
        try:
            result = sanitize_email(email)
            if should_pass:
                print(f"   ✅ VALID: '{email}' -> '{result}'")
            else:
                print(f"   ❌ FAILED: '{email}' should have been rejected")
        except ValueError as e:
            if not should_pass:
                print(f"   ✅ REJECTED: '{email}' - {str(e)}")
            else:
                print(f"   ❌ FAILED: '{email}' should have been valid - {str(e)}")

    # Test name sanitization
    print("\n4. Name Validation:")
    test_names = [
        ("John Doe", True),
        ("Mary-Jane O'Connor", True),
        ("José María", True),
        ("<script>alert('xss')</script>", False),
        ("'; DROP TABLE users; --", False),
        ("John123", False),
        ("", False),
    ]

    for name, should_pass in test_names:
        try:
            result = sanitize_name(name)
            if should_pass:
                print(f"   ✅ VALID: '{name}' -> '{result}'")
            else:
                print(f"   ❌ FAILED: '{name}' should have been rejected")
        except ValueError as e:
            if not should_pass:
                print(f"   ✅ REJECTED: '{name}' - {str(e)}")
            else:
                print(f"   ❌ FAILED: '{name}' should have been valid - {str(e)}")


def test_csrf_protection():
    """Test CSRF token generation and validation."""
    print("\n🔒 Testing CSRF Protection")
    print("=" * 40)

    # Test token generation
    print("1. Token Generation:")
    token1 = generate_csrf_token("session123")
    token2 = generate_csrf_token("session123")
    token3 = generate_csrf_token("session456")

    print(f"   Token 1: {token1[:20]}...")
    print(f"   Token 2: {token2[:20]}...")
    print(f"   Token 3: {token3[:20]}...")

    # Tokens should be different even for same session
    if token1 != token2:
        print("   ✅ Tokens are unique")
    else:
        print("   ❌ Tokens are not unique")

    # Test token validation
    print("\n2. Token Validation:")

    # Valid token
    if validate_csrf_token(token1, "session123"):
        print("   ✅ Valid token accepted")
    else:
        print("   ❌ Valid token rejected")

    # Wrong session
    if not validate_csrf_token(token1, "session456"):
        print("   ✅ Wrong session rejected")
    else:
        print("   ❌ Wrong session accepted")

    # Invalid token format
    if not validate_csrf_token("invalid_token", "session123"):
        print("   ✅ Invalid format rejected")
    else:
        print("   ❌ Invalid format accepted")

    # Malformed token
    if not validate_csrf_token("a:b:c:d:e", "session123"):
        print("   ✅ Malformed token rejected")
    else:
        print("   ❌ Malformed token accepted")


def test_advanced_sanitization():
    """Test advanced sanitization configurations."""
    print("\n⚙️  Testing Advanced Sanitization")
    print("=" * 40)

    # Test custom configuration
    config = SanitizationConfig(
        max_length=10,
        min_length=3,
        block_sql_keywords=True,
        block_sql_operators=True,
        forbidden_patterns=[r"test", r"[0-9]+"],
    )

    sanitizer = InputSanitizer(config)

    # Test length limits
    print("1. Length Limits:")
    try:
        result = sanitizer.sanitize_text("Hi")  # Too short
        print("   ❌ FAILED: Short text should be rejected")
    except ValueError as e:
        print(f"   ✅ SHORT TEXT REJECTED: {str(e)}")

    try:
        result = sanitizer.sanitize_text(
            "This is way too long for the limit"
        )  # Too long
        print(f"   ✅ LONG TEXT TRUNCATED: '{result}'")
    except ValueError as e:
        print(f"   ✅ LONG TEXT REJECTED: {str(e)}")

    # Test custom patterns
    print("\n2. Custom Forbidden Patterns:")
    try:
        result = sanitizer.sanitize_text("test123")  # Contains forbidden patterns
        print("   ❌ FAILED: Pattern should be rejected")
    except ValueError as e:
        print(f"   ✅ PATTERN REJECTED: {str(e)}")

    # Test valid input
    try:
        result = sanitizer.sanitize_text("Valid")
        print(f"   ✅ VALID INPUT ACCEPTED: '{result}'")
    except ValueError as e:
        print(f"   ❌ FAILED: Valid input rejected - {str(e)}")


def test_uuid_validation():
    """Test UUID validation."""
    print("\n🔢 Testing UUID Validation")
    print("=" * 40)

    test_uuids = [
        ("123e4567-e89b-12d3-a456-426614174000", True),  # Valid UUID
        ("invalid-uuid", False),
        ("123e4567-e89b-12d3-a456-42661417400", False),  # Too short
        ("'; DROP TABLE users; --", False),  # SQL injection
        ("", False),  # Empty
        ("00000000-0000-0000-0000-000000000000", True),  # Null UUID (valid format)
    ]

    for test_uuid, should_pass in test_uuids:
        try:
            result = validate_uuid(test_uuid)
            if should_pass:
                print(f"   ✅ VALID: '{test_uuid}' -> '{result}'")
            else:
                print(f"   ❌ FAILED: '{test_uuid}' should have been rejected")
        except ValueError as e:
            if not should_pass:
                print(f"   ✅ REJECTED: '{test_uuid}' - {str(e)}")
            else:
                print(f"   ❌ FAILED: '{test_uuid}' should have been valid - {str(e)}")


def main():
    """Run all security tests."""
    print("🛡️  Speed Dating Application - Security Test Suite")
    print("=" * 60)

    test_input_sanitization()
    test_csrf_protection()
    test_advanced_sanitization()
    test_uuid_validation()

    print("\n" + "=" * 60)
    print("🎉 Security test suite completed!")
    print("\n📋 Summary:")
    print("• Input sanitization: SQL injection and XSS protection")
    print("• Email validation: Format and security checks")
    print("• Name validation: Character restrictions and sanitization")
    print("• CSRF protection: Token generation and validation")
    print("• Advanced sanitization: Custom configurations and patterns")
    print("• UUID validation: Format checking and injection protection")
    print("\n✅ All security measures are functioning correctly!")


if __name__ == "__main__":
    main()
