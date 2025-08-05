"""
Documentation configuration and utilities.

This module provides configuration and helper functions for consistent
documentation generation and organization.
"""
import os
from pathlib import Path
from typing import Optional

from app.config import settings


class DocsConfig:
    """Configuration class for documentation settings."""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent  # Project root
        self.docs_dir = self.base_dir / settings.get("docs_directory", "docs")
        self.auto_generate = settings.get("auto_generate_docs", True)
        
        # Ensure docs directory exists
        self.docs_dir.mkdir(exist_ok=True)
    
    def get_docs_path(self, filename: str) -> Path:
        """Get the full path for a documentation file."""
        return self.docs_dir / filename
    
    def ensure_docs_dir_exists(self) -> None:
        """Ensure the documentation directory exists."""
        self.docs_dir.mkdir(exist_ok=True)
    
    def list_docs_files(self) -> list[str]:
        """List all documentation files in the docs directory."""
        if not self.docs_dir.exists():
            return []
        
        return [
            f.name for f in self.docs_dir.iterdir() 
            if f.is_file() and f.suffix.lower() == '.md'
        ]
    
    def get_doc_template_path(self, template_name: str) -> Path:
        """Get path for documentation templates."""
        templates_dir = self.docs_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        return templates_dir / template_name


# Global docs configuration instance
docs_config = DocsConfig()


def create_documentation_file(
    filename: str, 
    content: str, 
    overwrite: bool = False
) -> Path:
    """
    Create a documentation file in the docs directory.
    
    Args:
        filename: Name of the documentation file (should end with .md)
        content: Content to write to the file
        overwrite: Whether to overwrite existing files
        
    Returns:
        Path to the created file
        
    Raises:
        FileExistsError: If file exists and overwrite is False
    """
    if not filename.endswith('.md'):
        filename += '.md'
    
    file_path = docs_config.get_docs_path(filename)
    
    if file_path.exists() and not overwrite:
        raise FileExistsError(f"Documentation file {filename} already exists")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path


def update_documentation_file(filename: str, content: str) -> Path:
    """
    Update or create a documentation file in the docs directory.
    
    Args:
        filename: Name of the documentation file
        content: Content to write to the file
        
    Returns:
        Path to the updated file
    """
    return create_documentation_file(filename, content, overwrite=True)


def get_documentation_template(template_name: str) -> str:
    """
    Get a documentation template.
    
    Args:
        template_name: Name of the template
        
    Returns:
        Template content as string
    """
    templates = {
        "api_endpoint": """# {title}

## Overview
{description}

## Endpoints

### {method} {endpoint}
{endpoint_description}

**Request:**
```json
{request_example}
```

**Response:**
```json
{response_example}
```

## Authentication
{auth_requirements}

## Error Responses
{error_responses}

## Examples
{usage_examples}
""",
        
        "feature_guide": """# {feature_name}

## Overview
{overview}

## Features
{features_list}

## Usage
{usage_instructions}

## Configuration
{configuration_details}

## API Reference
{api_reference}

## Examples
{examples}

## Troubleshooting
{troubleshooting}
""",
        
        "system_architecture": """# {system_name} Architecture

## Overview
{overview}

## Components
{components_list}

## Data Flow
{data_flow_description}

## Security Considerations
{security_details}

## Performance Notes
{performance_notes}

## Deployment
{deployment_instructions}
"""
    }
    
    return templates.get(template_name, "")


# Convenience functions for common documentation tasks
def create_api_docs(filename: str, title: str, **kwargs) -> Path:
    """Create API documentation using the API template."""
    template = get_documentation_template("api_endpoint")
    content = template.format(title=title, **kwargs)
    return create_documentation_file(filename, content)


def create_feature_docs(filename: str, feature_name: str, **kwargs) -> Path:
    """Create feature documentation using the feature template."""
    template = get_documentation_template("feature_guide")
    content = template.format(feature_name=feature_name, **kwargs)
    return create_documentation_file(filename, content)


def create_architecture_docs(filename: str, system_name: str, **kwargs) -> Path:
    """Create architecture documentation using the architecture template."""
    template = get_documentation_template("system_architecture")
    content = template.format(system_name=system_name, **kwargs)
    return create_documentation_file(filename, content)