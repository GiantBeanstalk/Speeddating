# End-to-End Testing with Playwright

This directory contains comprehensive end-to-end tests for the Speed Dating application using Playwright for browser automation.

## Test Structure

```
tests/e2e/
├── conftest.py                 # Playwright fixtures and configuration
├── pages/                      # Page Object Model classes
│   ├── __init__.py
│   ├── base_page.py           # Base page with common functionality
│   ├── auth_pages.py          # Authentication pages
│   ├── admin_pages.py         # Admin dashboard pages
│   ├── attendee_pages.py      # Attendee interface pages
│   └── public_pages.py        # Public-facing pages
├── test_auth_flows.py         # Authentication testing
├── test_event_management.py   # Event management testing
├── test_realtime_features.py  # WebSocket and real-time testing
├── test_matching_system.py    # Matching algorithm UI testing
├── test_admin_dashboard.py    # Admin dashboard testing
├── test_cross_browser.py      # Multi-browser and mobile testing
└── README.md                  # This file
```

## Prerequisites

1. Install Playwright dependencies:
```bash
# From project root
source .venv/bin/activate
uv sync --group test
playwright install
```

2. Start the application:
```bash
# In one terminal
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Running Tests

### Basic Test Execution

```bash
# Run all E2E tests
pytest tests/e2e/ -m "e2e"

# Run specific test file
pytest tests/e2e/test_auth_flows.py -v

# Run specific test class
pytest tests/e2e/test_auth_flows.py::TestAuthenticationFlows -v

# Run specific test
pytest tests/e2e/test_auth_flows.py::TestAuthenticationFlows::test_user_registration_flow -v
```

### Browser-Specific Testing

```bash
# Run tests on specific browser (default: all browsers)
pytest tests/e2e/ --browser chromium
pytest tests/e2e/ --browser firefox  
pytest tests/e2e/ --browser webkit

# Run cross-browser compatibility tests
pytest tests/e2e/test_cross_browser.py -v
```

### Mobile Testing

```bash
# Run mobile viewport tests
pytest tests/e2e/test_cross_browser.py::TestMobileViewport -v
```

### Test Categories

```bash
# Run authentication tests
pytest tests/e2e/ -m "playwright" -k "auth"

# Run admin tests
pytest tests/e2e/ -m "playwright" -k "admin"

# Run real-time feature tests
pytest tests/e2e/ -m "playwright" -k "realtime"

# Run matching system tests
pytest tests/e2e/ -m "playwright" -k "matching"

# Run slow tests (comprehensive scenarios)
pytest tests/e2e/ -m "slow"
```

## Configuration

### Environment Variables

Set these environment variables to customize test behavior:

```bash
# Application URL (default: http://localhost:8000)
export E2E_BASE_URL="http://localhost:8000"

# Playwright options
export PLAYWRIGHT_HEADLESS="false"        # Show browser (default: true)
export PLAYWRIGHT_SLOW_MO="1000"          # Slow down actions (ms)
export PLAYWRIGHT_TRACE="true"            # Enable trace recording
export PLAYWRIGHT_DEBUG="true"            # Enable debug logging

# Test admin credentials
export TEST_ADMIN_EMAIL="admin@test.com"
export TEST_ADMIN_PASSWORD="AdminPassword123!"
```

### pytest.ini Configuration

The E2E tests use these pytest markers defined in `pyproject.toml`:

- `e2e`: End-to-end tests
- `playwright`: Playwright browser tests
- `slow`: Long-running comprehensive tests

## Test Data

Tests use realistic UK-based test data generated with Faker:

- **Email addresses**: UK format emails
- **Phone numbers**: UK mobile and landline numbers  
- **Names**: British names and locations
- **Events**: Realistic venues and timing
- **Profiles**: Authentic bio content and demographics

## Page Object Model

Tests use the Page Object Model pattern for maintainability:

### Base Page (base_page.py)
Common functionality shared by all pages:
- Navigation helpers
- Element interaction methods
- Assertion helpers
- Screenshot capture
- Wait conditions

### Authentication Pages (auth_pages.py)
- `LoginPage`: Login form interactions
- `RegisterPage`: User registration
- `ForgotPasswordPage`: Password reset request
- `ResetPasswordPage`: Password reset completion

### Admin Pages (admin_pages.py)
- `AdminDashboardPage`: Admin overview and statistics
- `EventManagementPage`: Create, edit, delete events
- `AttendeeManagementPage`: Manage event attendees

### Attendee Pages (attendee_pages.py)
- `AttendeeDashboardPage`: Attendee dashboard
- `MatchingPage`: Speed dating matching interface
- `ProfilePage`: Profile editing and viewing

### Public Pages (public_pages.py)
- `HomePage`: Landing page
- `EventListPage`: Browse available events
- `PublicProfilePage`: View public profiles via QR

## Test Categories

### 1. Authentication Tests (`test_auth_flows.py`)
- User registration and validation
- Login/logout functionality
- Password reset flow
- Session management
- Security testing (XSS, CSRF protection)

### 2. Event Management Tests (`test_event_management.py`)
- Event creation, editing, deletion
- Event form validation
- Attendee registration flow
- Event search and filtering
- Capacity management

### 3. Real-time Features (`test_realtime_features.py`)
- WebSocket connectivity
- Countdown timers
- Round management
- Real-time notifications
- Multi-user synchronization
- Connection error handling

### 4. Matching System (`test_matching_system.py`)
- Matching interface functionality
- Like/pass/maybe actions
- Match notifications
- Profile interactions
- Algorithm behavior testing
- Preference persistence

### 5. Admin Dashboard (`test_admin_dashboard.py`)
- Dashboard overview and statistics
- Quick actions and shortcuts
- Bulk operations
- Access control and security
- Export functionality
- Performance testing

### 6. Cross-browser Testing (`test_cross_browser.py`)
- Multi-browser compatibility (Chromium, Firefox, WebKit)
- Mobile viewport testing
- Touch interactions
- Responsive design
- Accessibility features
- Performance across browsers

## Debugging

### Visual Debugging

```bash
# Run with visible browser
PLAYWRIGHT_HEADLESS=false pytest tests/e2e/test_auth_flows.py -v

# Slow down actions for observation
PLAYWRIGHT_SLOW_MO=2000 pytest tests/e2e/test_auth_flows.py -v
```

### Screenshots and Traces

```bash
# Enable tracing (creates trace.zip)
PLAYWRIGHT_TRACE=true pytest tests/e2e/test_auth_flows.py -v

# View trace file
playwright show-trace trace.zip
```

Screenshots are automatically captured on test failures and saved to `test-results/screenshots/`.

### Debug Logging

```bash
# Enable detailed logging
PLAYWRIGHT_DEBUG=true pytest tests/e2e/ -v -s
```

## Continuous Integration

For CI/CD integration:

```bash
# Headless mode with minimal output
pytest tests/e2e/ --browser chromium --maxfail=5 --tb=short

# Parallel execution
pytest tests/e2e/ -n auto --dist worksteal

# Generate reports
pytest tests/e2e/ --html=test-results/e2e-report.html --self-contained-html
```

## Best Practices

### Test Isolation
- Each test starts with a clean browser context
- Tests use unique test data (Faker-generated)
- Database state is isolated between tests

### Reliability
- Proper wait conditions instead of sleep()
- Robust selectors that work across browsers
- Graceful handling of timing issues
- Retry mechanisms for flaky operations

### Maintainability
- Page Object Model for UI abstraction
- Reusable fixtures and helpers
- Clear test naming and documentation
- Parameterized tests for browser coverage

### Performance
- Parallel test execution where possible
- Efficient element selection strategies
- Minimal test data setup
- Smart waiting strategies

## Common Issues and Solutions

### Test Timeouts
- Increase timeout for slow operations: `await page.wait_for_selector(selector, timeout=30000)`
- Use network idle waiting: `await page.wait_for_load_state("networkidle")`

### Element Not Found
- Use more specific selectors
- Add wait conditions before interactions
- Check for element visibility: `await expect(page.locator(selector)).to_be_visible()`

### Flaky Tests
- Add proper wait conditions
- Use retry mechanisms for unreliable operations
- Verify test data setup

### Cross-browser Issues
- Test-specific browser capabilities
- Handle browser-specific behaviors
- Use progressive enhancement strategies

## Contributing

When adding new E2E tests:

1. Follow the Page Object Model pattern
2. Use realistic test data with Faker
3. Include proper error handling and waits
4. Test across multiple browsers
5. Document any special setup requirements
6. Add appropriate test markers
7. Include both positive and negative test cases