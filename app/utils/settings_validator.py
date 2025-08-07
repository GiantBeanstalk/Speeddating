"""
Settings validation and health check utilities.

Provides comprehensive validation of application settings and configuration
with detailed error reporting and security checks.
"""

import re
import socket
from typing import Any
from urllib.parse import urlparse

from dynaconf import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings


class SettingsHealthCheck:
    """Comprehensive settings validation and health checking."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def validate_all(self) -> dict[str, Any]:
        """
        Validate all settings and return comprehensive report.

        Returns:
            Dictionary with validation results, errors, warnings, and info
        """
        self.errors.clear()
        self.warnings.clear()
        self.info.clear()

        # Core validation
        self._validate_security_settings()
        self._validate_database_settings()
        self._validate_server_settings()
        self._validate_email_settings()
        self._validate_application_settings()

        # Environment-specific validation
        self._validate_environment_specific()

        # Connectivity tests
        self._test_database_connection()
        self._test_smtp_connection()

        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "summary": self._generate_summary(),
        }

    def _validate_security_settings(self) -> None:
        """Validate security-related settings."""
        try:
            secret_key = settings.get("SECRET_KEY")
            if not secret_key:
                self.errors.append("SECRET_KEY is not set")
            elif len(secret_key) < 32:
                self.errors.append("SECRET_KEY is too short (minimum 32 characters)")
            elif secret_key == "your-secret-key-here-change-in-production":
                if settings.get("ENV") == "production":
                    self.errors.append(
                        "SECRET_KEY must be changed from default in production"
                    )
                else:
                    self.warnings.append(
                        "SECRET_KEY is using default value (change for production)"
                    )
            else:
                self.info.append("SECRET_KEY is properly configured")
        except Exception as e:
            self.errors.append(f"Error validating SECRET_KEY: {str(e)}")

    def _validate_database_settings(self) -> None:
        """Validate database configuration."""
        try:
            db_url = settings.get("DATABASE_URL")
            if not db_url:
                self.errors.append("DATABASE_URL is not set")
                return

            # Parse URL
            try:
                parsed = urlparse(db_url)
                if not parsed.scheme:
                    self.errors.append(
                        "DATABASE_URL missing scheme (e.g., sqlite+aiosqlite)"
                    )
                elif parsed.scheme not in [
                    "sqlite+aiosqlite",
                    "postgresql+asyncpg",
                    "mysql+aiomysql",
                ]:
                    self.warnings.append(
                        f"DATABASE_URL uses uncommon scheme: {parsed.scheme}"
                    )
                else:
                    self.info.append(f"Database configured: {parsed.scheme}")

                # SQLite specific checks
                if "sqlite" in parsed.scheme:
                    if not parsed.path or parsed.path == "/":
                        self.errors.append(
                            "SQLite DATABASE_URL missing database file path"
                        )
                    else:
                        self.info.append(f"SQLite database file: {parsed.path}")

                # PostgreSQL/MySQL checks
                elif parsed.scheme in ["postgresql+asyncpg", "mysql+aiomysql"]:
                    if not parsed.hostname:
                        self.errors.append("Database URL missing hostname")
                    if not parsed.username:
                        self.warnings.append("Database URL missing username")
                    if not parsed.password:
                        self.warnings.append(
                            "Database URL missing password (may be in environment)"
                        )

            except Exception as e:
                self.errors.append(f"Invalid DATABASE_URL format: {str(e)}")

        except Exception as e:
            self.errors.append(f"Error validating database settings: {str(e)}")

    def _validate_server_settings(self) -> None:
        """Validate server and network settings."""
        try:
            # Host validation
            host = settings.get("HOST", "127.0.0.1")
            try:
                socket.inet_aton(host)  # Validate IPv4
                self.info.append(f"Server host: {host}")
            except OSError:
                if host in ["localhost", "0.0.0.0"]:
                    self.info.append(f"Server host: {host}")
                else:
                    self.warnings.append(f"Host may be invalid: {host}")

            # Port validation
            port = settings.get("PORT", 8000)
            if not isinstance(port, int) or not (1 <= port <= 65535):
                self.errors.append(f"Invalid PORT: {port}")
            elif port < 1024 and port != 80 and port != 443:
                self.warnings.append(f"Using privileged port {port} (may require sudo)")
            else:
                self.info.append(f"Server port: {port}")

            # CORS validation
            allowed_origins = settings.get("ALLOWED_ORIGINS", [])
            if not isinstance(allowed_origins, list):
                self.errors.append("ALLOWED_ORIGINS must be a list")
            elif "*" in allowed_origins:
                if settings.get("ENV") == "production":
                    self.errors.append(
                        "ALLOWED_ORIGINS cannot contain '*' in production"
                    )
                else:
                    self.warnings.append(
                        "ALLOWED_ORIGINS contains '*' (development only)"
                    )
            else:
                self.info.append(
                    f"CORS origins configured: {len(allowed_origins)} domains"
                )

        except Exception as e:
            self.errors.append(f"Error validating server settings: {str(e)}")

    def _validate_email_settings(self) -> None:
        """Validate email/SMTP configuration."""
        try:
            smtp_host = settings.get("SMTP_HOST")
            smtp_username = settings.get("SMTP_USERNAME")

            if not smtp_host and not smtp_username:
                self.info.append(
                    "Email not configured (password reset will use console output)"
                )
                return

            if smtp_host and not smtp_username:
                self.warnings.append("SMTP_HOST set but SMTP_USERNAME missing")
            elif smtp_username and not smtp_host:
                self.warnings.append("SMTP_USERNAME set but SMTP_HOST missing")

            if smtp_host:
                # Validate SMTP port
                smtp_port = settings.get("SMTP_PORT", 587)
                if not isinstance(smtp_port, int) or not (1 <= smtp_port <= 65535):
                    self.errors.append(f"Invalid SMTP_PORT: {smtp_port}")
                else:
                    self.info.append(f"SMTP server: {smtp_host}:{smtp_port}")

                # Validate from email
                from_email = settings.get("SMTP_FROM_EMAIL", "noreply@speeddating.app")
                if not re.match(
                    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", from_email
                ):
                    self.errors.append(f"Invalid SMTP_FROM_EMAIL format: {from_email}")
                else:
                    self.info.append(f"Email from address: {from_email}")

        except Exception as e:
            self.errors.append(f"Error validating email settings: {str(e)}")

    def _validate_application_settings(self) -> None:
        """Validate application-specific settings."""
        try:
            # QR code base URL
            qr_base_url = settings.get("QR_CODE_BASE_URL", "http://localhost:8000")
            if not qr_base_url.startswith(("http://", "https://")):
                self.errors.append(
                    "QR_CODE_BASE_URL must start with http:// or https://"
                )
            else:
                self.info.append(f"QR code base URL: {qr_base_url}")

            # PDF settings
            badges_per_page = settings.get("PDF_BADGES_PER_PAGE", 35)
            if not isinstance(badges_per_page, int) or not (
                1 <= badges_per_page <= 100
            ):
                self.errors.append(
                    f"PDF_BADGES_PER_PAGE must be between 1 and 100, got: {badges_per_page}"
                )
            else:
                self.info.append(f"PDF badges per page: {badges_per_page}")

        except Exception as e:
            self.errors.append(f"Error validating application settings: {str(e)}")

    def _validate_environment_specific(self) -> None:
        """Validate environment-specific requirements."""
        try:
            env = settings.get("ENV", "development")
            debug = settings.get("DEBUG", False)

            if env == "production":
                if debug:
                    self.errors.append("DEBUG must be False in production")

                # Check for development-only settings
                if settings.get("DATABASE_ECHO", False):
                    self.warnings.append("DATABASE_ECHO should be False in production")

                self.info.append("Production environment validation completed")
            else:
                self.info.append(f"Environment: {env}")

        except Exception as e:
            self.errors.append(f"Error validating environment settings: {str(e)}")

    def _test_database_connection(self) -> None:
        """Test database connectivity."""
        try:
            db_url = settings.get("DATABASE_URL")
            if not db_url:
                return

            # Convert async URL to sync for testing
            sync_url = (
                db_url.replace("+aiosqlite", "")
                .replace("+asyncpg", "+psycopg2")
                .replace("+aiomysql", "+pymysql")
            )

            # Create test engine
            test_engine = create_engine(sync_url)

            # Test connection
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self.info.append("Database connection test successful")
            test_engine.dispose()

        except SQLAlchemyError as e:
            self.warnings.append(f"Database connection test failed: {str(e)}")
        except Exception as e:
            self.warnings.append(f"Could not test database connection: {str(e)}")

    def _test_smtp_connection(self) -> None:
        """Test SMTP connectivity."""
        try:
            smtp_host = settings.get("SMTP_HOST")
            if not smtp_host:
                return

            import socket

            smtp_port = settings.get("SMTP_PORT", 587)

            # Test socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5 second timeout
            result = sock.connect_ex((smtp_host, smtp_port))
            sock.close()

            if result == 0:
                self.info.append("SMTP server connectivity test successful")
            else:
                self.warnings.append(
                    f"Cannot connect to SMTP server {smtp_host}:{smtp_port}"
                )

        except Exception as e:
            self.warnings.append(f"Could not test SMTP connection: {str(e)}")

    def _generate_summary(self) -> str:
        """Generate validation summary."""
        if len(self.errors) > 0:
            return f"❌ Configuration has {len(self.errors)} error(s) and {len(self.warnings)} warning(s)"
        elif len(self.warnings) > 0:
            return f"⚠️  Configuration has {len(self.warnings)} warning(s) but no errors"
        else:
            return f"✅ Configuration is valid ({len(self.info)} checks passed)"


def validate_settings() -> dict[str, Any]:
    """
    Validate all application settings.

    Returns:
        Validation report dictionary
    """
    checker = SettingsHealthCheck()
    return checker.validate_all()


def print_validation_report() -> bool:
    """
    Print detailed validation report to console.

    Returns:
        True if validation passed, False if there were errors
    """
    print("🔧 Settings Validation Report")
    print("=" * 50)

    try:
        report = validate_settings()

        # Print summary
        print(f"\n{report['summary']}")

        # Print errors
        if report["errors"]:
            print(f"\n❌ ERRORS ({len(report['errors'])}):")
            for i, error in enumerate(report["errors"], 1):
                print(f"  {i}. {error}")

        # Print warnings
        if report["warnings"]:
            print(f"\n⚠️  WARNINGS ({len(report['warnings'])}):")
            for i, warning in enumerate(report["warnings"], 1):
                print(f"  {i}. {warning}")

        # Print info
        if report["info"]:
            print(f"\n✅ PASSED ({len(report['info'])}):")
            for i, info in enumerate(report["info"], 1):
                print(f"  {i}. {info}")

        print("\n" + "=" * 50)
        return report["valid"]

    except ValidationError as e:
        print(f"\n❌ Configuration validation failed: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error during validation: {str(e)}")
        return False


if __name__ == "__main__":
    """Run validation when script is executed directly."""
    import sys

    success = print_validation_report()
    sys.exit(0 if success else 1)
