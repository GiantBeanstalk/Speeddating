# Speed Dating Application Documentation

This directory contains comprehensive documentation for the Speed Dating Application.

## Documentation Structure

### Core Documentation
- **[API_MODELS_GUIDE.md](API_MODELS_GUIDE.md)** - Complete API endpoints and data model documentation
- **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)** - Database schema, relationships, and migrations
- **[ER_DIAGRAM.md](ER_DIAGRAM.md)** - Entity relationship diagrams and data flow
- **[MODEL_TESTING.md](MODEL_TESTING.md)** - Model testing strategies and examples
- **[REALTIME_SYSTEM.md](REALTIME_SYSTEM.md)** - WebSocket real-time features and countdown system

## Documentation Standards

### File Naming Convention
- Use `UPPER_CASE_WITH_UNDERSCORES.md` for system documentation
- Use `kebab-case.md` for feature-specific guides
- Use descriptive names that clearly indicate content

### Content Structure
All documentation should follow this structure:

```markdown
# Title

## Overview
Brief description of the feature/system

## Key Features
- Bullet points of main features

## Usage/Implementation
Detailed usage instructions or implementation details

## API Reference (if applicable)
Endpoint documentation with examples

## Examples
Code examples and use cases

## Troubleshooting (if applicable)
Common issues and solutions
```

### Code Examples
- Always use proper syntax highlighting
- Include complete, working examples
- Show both request and response formats for APIs
- Include error handling examples

## Auto-Generated Documentation

The application is configured to automatically generate documentation in this folder. The configuration is managed through:

- **Settings**: `settings.toml` contains `docs_directory = "docs"`
- **Utils**: `app/utils/docs_config.py` provides documentation utilities
- **Templates**: Pre-defined templates for consistent documentation

### Creating New Documentation

Use the documentation utilities for consistent formatting:

```python
from app.utils import create_api_docs, create_feature_docs

# Create API documentation
create_api_docs(
    filename="new_api_guide.md",
    title="New API Feature",
    description="Description of the new API",
    # ... other parameters
)

# Create feature documentation
create_feature_docs(
    filename="new_feature_guide.md",
    feature_name="New Feature",
    overview="Feature overview",
    # ... other parameters
)
```

## Documentation Guidelines

### Keep Documentation Updated
- Update documentation when adding new features
- Review and update existing docs when making changes
- Include documentation updates in pull requests

### Write for Your Audience
- **API docs**: For developers integrating with the API
- **System docs**: For developers working on the codebase
- **Feature docs**: For users and administrators

### Include Examples
- Always provide working code examples
- Show common use cases and edge cases
- Include error handling and validation examples

### Test Your Examples
- Ensure all code examples actually work
- Test API endpoints and verify responses
- Update examples when APIs change

## Quick Reference

### Common Documentation Tasks

1. **Adding a new API endpoint**: Update `API_MODELS_GUIDE.md` and create specific endpoint docs if complex
2. **Adding a database model**: Update `DATABASE_SCHEMA.md` and `ER_DIAGRAM.md`
3. **Adding a new feature**: Create feature-specific documentation using templates
4. **System changes**: Update relevant system documentation and architecture docs

### Documentation Tools

- **Markdown**: All documentation uses GitHub-flavored Markdown
- **Mermaid**: For diagrams and flowcharts (supported in most Markdown renderers)
- **Code blocks**: Use proper language tags for syntax highlighting
- **Links**: Use relative links within documentation

## Contributing to Documentation

1. **Check existing documentation** first to avoid duplication
2. **Use the templates** provided in `docs_config.py`
3. **Follow the naming conventions** and structure standards
4. **Test all examples** before submitting
5. **Update the README** if adding new documentation categories

## Documentation Maintenance

Documentation is a living resource that should be maintained alongside the codebase:

- Review documentation quarterly for accuracy
- Update when APIs or features change
- Remove or update deprecated information
- Ensure examples work with current code

---

For questions about documentation or to suggest improvements, please refer to the main project README or create an issue in the project repository.