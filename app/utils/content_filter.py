"""
Content filtering utilities for user-generated content.

Filters out URLs, phone numbers, and other inappropriate content from bio fields.
"""

import re


class ContentFilterResult:
    """Result of content filtering operation."""

    def __init__(self, cleaned_content: str, violations: list[str], is_valid: bool):
        self.cleaned_content = cleaned_content
        self.violations = violations
        self.is_valid = is_valid

    @property
    def violation_message(self) -> str:
        """Get user-friendly violation message."""
        if not self.violations:
            return ""

        return (
            "Your bio contains content that is not allowed: "
            + ", ".join(self.violations)
            + ". Please remove URLs, phone numbers, and contact information from your bio. "
            + "Contact details should be provided in the designated contact fields."
        )


class BioContentFilter:
    """Filter for bio content to ensure it's appropriate and safe."""

    def __init__(self):
        # URL patterns - comprehensive regex to catch various URL formats
        self.url_patterns = [
            # Standard HTTP/HTTPS URLs
            r"https?://[^\s]+",
            # www.domain.com
            r"www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?",
            # domain.com (with common TLDs)
            r"[a-zA-Z0-9.-]+\.(?:com|org|net|edu|gov|co\.uk|io|me|tv|info|biz|name|mobi|pro|tel|travel|xxx|adult)(?:/[^\s]*)?",
            # Email-like patterns that might be URLs
            r"[a-zA-Z0-9.-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            # Social media handles that might be interpreted as URLs
            r"(?:instagram\.com/|twitter\.com/|facebook\.com/|tiktok\.com/@|linkedin\.com/in/)[a-zA-Z0-9._-]+",
            # Shortened URLs
            r"(?:bit\.ly|tinyurl\.com|t\.co|short\.link|goo\.gl)/[a-zA-Z0-9]+",
            # Alternative protocols
            r"(?:ftp|ftps|file)://[^\s]+",
        ]

        # Phone number patterns - UK and international
        self.phone_patterns = [
            # UK mobile numbers
            r"(?:\+44\s?|0)7[0-9]{3}\s?[0-9]{3}\s?[0-9]{3}",
            # UK landlines
            r"(?:\+44\s?|0)(?:1[0-9]{2,4}|2[0-9])\s?[0-9]{3,4}\s?[0-9]{3,4}",
            # International numbers
            r"\+[1-9][0-9]{1,3}\s?[0-9]{3,14}",
            # Generic phone patterns
            r"(?:\+?[0-9]{1,3}[-.\s]?)?(?:\([0-9]{1,4}\)[-.\s]?)?[0-9]{3,4}[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{0,4}",
            # Phone numbers in various formats
            r"[0-9]{3,4}[-.\s][0-9]{3,4}[-.\s][0-9]{3,4}",
            r"\([0-9]{3,4}\)\s?[0-9]{3,4}[-.\s]?[0-9]{3,4}",
        ]

        # Social media handle patterns
        self.social_patterns = [
            r"@[a-zA-Z0-9._-]+",  # @username
            r"instagram:\s*[a-zA-Z0-9._-]+",
            r"twitter:\s*[a-zA-Z0-9._-]+",
            r"facebook:\s*[a-zA-Z0-9._-]+",
            r"snap(?:chat)?:\s*[a-zA-Z0-9._-]+",
            r"tiktok:\s*[a-zA-Z0-9._-]+",
            r"kik:\s*[a-zA-Z0-9._-]+",
            r"whatsapp:\s*[a-zA-Z0-9._-]+",
            r"telegram:\s*[a-zA-Z0-9._-]+",
        ]

        # Contact information patterns
        self.contact_patterns = [
            r"contact\s+me\s+(?:at|on)",
            r"message\s+me\s+(?:at|on)",
            r"find\s+me\s+(?:at|on)",
            r"add\s+me\s+(?:at|on)",
            r"follow\s+me\s+(?:at|on)",
            r"dm\s+me",
            r"text\s+me",
            r"call\s+me",
            r"email\s+me",
        ]

    def filter_bio(self, bio: str) -> ContentFilterResult:
        """
        Filter bio content and return cleaned version with violations.

        Args:
            bio: The bio text to filter

        Returns:
            ContentFilterResult with cleaned content and violation details
        """
        if not bio:
            return ContentFilterResult("", [], True)

        violations = []
        cleaned_bio = bio.strip()
        # original_bio = cleaned_bio  # unused variable

        # Check for URLs
        url_found = False
        for pattern in self.url_patterns:
            matches = re.findall(pattern, cleaned_bio, re.IGNORECASE)
            if matches:
                url_found = True
                # Remove the URLs
                cleaned_bio = re.sub(
                    pattern, "[REMOVED]", cleaned_bio, flags=re.IGNORECASE
                )

        if url_found:
            violations.append("website URLs and links")

        # Check for phone numbers
        phone_found = False
        for pattern in self.phone_patterns:
            matches = re.findall(pattern, cleaned_bio, re.IGNORECASE)
            if matches:
                phone_found = True
                # Remove phone numbers
                cleaned_bio = re.sub(
                    pattern, "[REMOVED]", cleaned_bio, flags=re.IGNORECASE
                )

        if phone_found:
            violations.append("phone numbers")

        # Check for social media handles
        social_found = False
        for pattern in self.social_patterns:
            matches = re.findall(pattern, cleaned_bio, re.IGNORECASE)
            if matches:
                social_found = True
                # Remove social handles
                cleaned_bio = re.sub(
                    pattern, "[REMOVED]", cleaned_bio, flags=re.IGNORECASE
                )

        if social_found:
            violations.append("social media handles")

        # Check for contact instructions
        contact_found = False
        for pattern in self.contact_patterns:
            if re.search(pattern, cleaned_bio, re.IGNORECASE):
                contact_found = True
                break

        if contact_found:
            violations.append("contact instructions")

        # Clean up multiple spaces and [REMOVED] placeholders
        cleaned_bio = re.sub(r"\[REMOVED\]", "", cleaned_bio)
        cleaned_bio = re.sub(r"\s+", " ", cleaned_bio).strip()

        # Check if content is significantly different (indicating violations)
        is_valid = len(violations) == 0

        # If we removed content, use original bio for violation checking
        # but return cleaned bio for reference
        return ContentFilterResult(
            cleaned_content=cleaned_bio, violations=violations, is_valid=is_valid
        )

    def validate_bio(self, bio: str, max_length: int = 500) -> tuple[bool, str]:
        """
        Validate bio content and return success status with message.

        Args:
            bio: The bio text to validate
            max_length: Maximum allowed length

        Returns:
            Tuple of (is_valid, message)
        """
        if not bio:
            return True, ""

        if len(bio) > max_length:
            return False, f"Bio must be {max_length} characters or less"

        filter_result = self.filter_bio(bio)

        if not filter_result.is_valid:
            return False, filter_result.violation_message

        return True, "Bio is valid"

    def get_safe_bio_suggestions(self) -> list[str]:
        """Get suggestions for appropriate bio content."""
        return [
            "Share your interests and hobbies",
            "Describe your personality",
            "Mention what you're looking for",
            "Talk about your favorite activities",
            "Share fun facts about yourself",
            "Describe your lifestyle or values",
            "Mention your profession (if comfortable)",
            "Share what makes you unique",
        ]

    def get_bio_guidelines(self) -> dict[str, list[str]]:
        """Get guidelines for bio content."""
        return {
            "allowed": [
                "Personal interests and hobbies",
                "Personality descriptions",
                "What you're looking for in matches",
                "Fun facts about yourself",
                "Your lifestyle and values",
                "Professional background (optional)",
                "Favorite activities or entertainment",
            ],
            "not_allowed": [
                "Website URLs or links",
                "Phone numbers",
                "Social media handles (@username)",
                "Email addresses",
                "Contact instructions ('message me at...')",
                "External platform references",
                "Any form of contact information",
            ],
            "tips": [
                "Keep it positive and engaging",
                "Be authentic and honest",
                "Use proper spelling and grammar",
                "Avoid negative language",
                "Focus on what makes you interesting",
                "Contact info goes in the contact fields, not the bio",
            ],
        }


# Global content filter instance
bio_filter = BioContentFilter()
