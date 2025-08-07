"""
Playwright-specific test configuration and fixtures.

Provides browser automation setup, page objects, and E2E test utilities
for comprehensive browser testing of the Speed Dating application.
"""

import asyncio
import os
import pytest
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
from faker import Faker
from typing import AsyncGenerator, Generator

# Set test environment for E2E tests
os.environ["SPEEDDATING_ENV"] = "testing"

# Test application URL (can be overridden with pytest --base-url)
BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def playwright() -> AsyncGenerator[Playwright, None]:
    """Create Playwright instance for the session."""
    async with async_playwright() as p:
        yield p


@pytest.fixture(scope="session", params=["chromium", "firefox", "webkit"])
async def browser(playwright: Playwright, request) -> AsyncGenerator[Browser, None]:
    """Create browser instance for each browser type."""
    browser_name = request.param
    
    # Browser launch options
    launch_options = {
        "headless": os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
        "slow_mo": int(os.getenv("PLAYWRIGHT_SLOW_MO", "0")),
    }
    
    if browser_name == "chromium":
        browser = await playwright.chromium.launch(**launch_options)
    elif browser_name == "firefox":
        browser = await playwright.firefox.launch(**launch_options)
    elif browser_name == "webkit":
        browser = await playwright.webkit.launch(**launch_options)
    else:
        raise ValueError(f"Unknown browser: {browser_name}")
    
    yield browser
    await browser.close()


@pytest.fixture
async def context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
    """Create browser context with realistic settings."""
    context = await browser.new_context(
        # Simulate realistic viewport
        viewport={"width": 1280, "height": 720},
        # Simulate realistic user agent
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Enable JavaScript
        java_script_enabled=True,
        # Accept downloads
        accept_downloads=True,
        # Realistic locale
        locale="en-GB",
        timezone_id="Europe/London",
        # Enable permissions needed for testing
        permissions=["notifications", "clipboard-read", "clipboard-write"],
    )
    
    # Set up network recording if needed
    if os.getenv("PLAYWRIGHT_TRACE", "false").lower() == "true":
        await context.tracing.start(screenshots=True, snapshots=True, sources=True)
    
    yield context
    
    # Stop tracing if enabled
    if os.getenv("PLAYWRIGHT_TRACE", "false").lower() == "true":
        await context.tracing.stop(path="trace.zip")
    
    await context.close()


@pytest.fixture
async def mobile_context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
    """Create mobile browser context for responsive testing."""
    context = await browser.new_context(
        **playwright.devices["iPhone 12"],  # Mobile device simulation
        locale="en-GB",
        timezone_id="Europe/London",
    )
    yield context
    await context.close()


@pytest.fixture
async def page(context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Create page instance."""
    page = await context.new_page()
    
    # Set up console logging
    page.on("console", lambda msg: print(f"Console {msg.type}: {msg.text}"))
    
    # Set up error logging
    page.on("pageerror", lambda error: print(f"Page error: {error}"))
    
    # Set up request/response logging for debugging
    if os.getenv("PLAYWRIGHT_DEBUG", "false").lower() == "true":
        page.on("request", lambda request: print(f"Request: {request.method} {request.url}"))
        page.on("response", lambda response: print(f"Response: {response.status} {response.url}"))
    
    yield page
    await page.close()


@pytest.fixture
async def mobile_page(mobile_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Create mobile page instance."""
    page = await mobile_context.new_page()
    yield page
    await page.close()


@pytest.fixture
def faker_instance() -> Faker:
    """Create Faker instance for E2E test data."""
    fake = Faker("en_GB")
    fake.seed_instance(42)  # Consistent seed for reproducible tests
    return fake


@pytest.fixture
def base_url() -> str:
    """Base URL for the application."""
    return BASE_URL


@pytest.fixture
async def authenticated_page(page: Page, base_url: str, faker_instance: Faker) -> AsyncGenerator[Page, None]:
    """Create an authenticated page session with a test user."""
    # Navigate to login page
    await page.goto(f"{base_url}/auth/login")
    
    # Create test credentials
    test_email = faker_instance.email()
    test_password = "TestPassword123!"
    
    # Register a test user first (assuming registration is available)
    await page.goto(f"{base_url}/auth/register")
    
    # Fill registration form (adjust selectors based on actual form)
    await page.fill("input[name='email']", test_email)
    await page.fill("input[name='password']", test_password)
    await page.fill("input[name='password_confirm']", test_password)
    
    # Submit registration
    await page.click("button[type='submit']")
    
    # Wait for successful registration or login
    await page.wait_for_url("**/dashboard**", timeout=10000)
    
    yield page


@pytest.fixture
async def admin_page(page: Page, base_url: str) -> AsyncGenerator[Page, None]:
    """Create an admin/organizer authenticated page session."""
    # This would use admin credentials or create an admin user
    # Implementation depends on your admin setup process
    await page.goto(f"{base_url}/auth/login")
    
    # Use admin credentials (these should be set up in test environment)
    admin_email = os.getenv("TEST_ADMIN_EMAIL", "admin@test.com")
    admin_password = os.getenv("TEST_ADMIN_PASSWORD", "AdminPassword123!")
    
    await page.fill("input[name='email']", admin_email)
    await page.fill("input[name='password']", admin_password)
    await page.click("button[type='submit']")
    
    # Wait for admin dashboard
    await page.wait_for_url("**/admin**", timeout=10000)
    
    yield page


# Screenshot capture on test failure
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture screenshots on test failure."""
    outcome = yield
    rep = outcome.get_result()
    
    if rep.when == "call" and rep.failed:
        # Get the page fixture if it exists
        if "page" in item.fixturenames:
            page = item.funcargs.get("page")
            if page:
                # Create screenshots directory
                screenshot_dir = "test-results/screenshots"
                os.makedirs(screenshot_dir, exist_ok=True)
                
                # Generate screenshot filename
                test_name = item.nodeid.replace("::", "_").replace("/", "_")
                screenshot_path = f"{screenshot_dir}/{test_name}.png"
                
                try:
                    # Take screenshot asynchronously
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Create a new task to take screenshot
                        task = asyncio.create_task(page.screenshot(path=screenshot_path))
                        # Don't wait for completion to avoid blocking
                    else:
                        loop.run_until_complete(page.screenshot(path=screenshot_path))
                    
                    print(f"Screenshot saved: {screenshot_path}")
                except Exception as e:
                    print(f"Failed to capture screenshot: {e}")


# Test data cleanup
@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Automatically clean up test data after each test."""
    yield
    
    # Add cleanup logic here if needed
    # For example, clearing test database entries, removing uploaded files, etc.
    pass