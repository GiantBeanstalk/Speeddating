# Claude Development Notes - Speed Dating Application

## Project Overview
This is a comprehensive Speed Dating application built with FastAPI, featuring:
- OAuth2 authentication with Google/Facebook
- Category-aware matching algorithm with reciprocal preferences
- QR code-based fast login system
- Real-time WebSocket features for countdowns and round management
- PDF badge generation
- Comprehensive testing infrastructure

## Important Development Reminders

### Virtual Environment
**ALWAYS activate the virtual environment before running any scripts or tests:**
```bash
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate     # On Windows
```

### Running Tests
```bash
# Activate virtual environment first!
source .venv/bin/activate

# Run all tests
python -m pytest

# Run specific test categories
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/property/ -v

# Run with coverage
python -m pytest --cov=app --cov-report=html
```

### Code Quality
```bash
# Activate virtual environment first!
source .venv/bin/activate

# Run linting
ruff check .

# Run type checking (if mypy is installed)
mypy app/

# Run pre-commit hooks
pre-commit run --all-files
```

## Project Structure
```
app/
├── api/          # FastAPI endpoints
├── models/       # SQLAlchemy models
├── services/     # Business logic services
├── utils/        # Utility functions
└── config/       # Configuration management

tests/
├── unit/         # Unit tests
├── integration/  # Integration tests
├── property/     # Property-based tests
└── fixtures/     # Test fixtures and providers
```

## Key Components

### Authentication System
- FastAPI-Users with JWT tokens
- OAuth2 integration (Google, Facebook)
- Role-based access (organizers, superusers)
- QR code fast login for attendees

### Matching Algorithm
- Category-aware pairing (Top/Bottom Male/Female)
- Reciprocal preference optimization
- Capacity balancing across categories
- Fair rotation across multiple rounds

### Testing Infrastructure
- pytest with async support
- Hypothesis for property-based testing
- Custom Faker providers for UK demographics
- Comprehensive test coverage requirements

## Development Workflow
1. **Always activate virtual environment first**
2. Run tests before making changes
3. Fix any linting issues with ruff
4. Commit with descriptive messages
5. Run full test suite before pushing

## Security Considerations
- All inputs validated and sanitized
- SQL injection protection
- Rate limiting on authentication endpoints
- Secure token handling for QR codes
- Content filtering for user-generated content