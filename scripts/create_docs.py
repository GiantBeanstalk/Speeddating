#!/usr/bin/env python3
"""
Documentation creation script.

This script helps developers create properly formatted documentation
in the correct location with consistent structure.
"""
import argparse
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.docs_config import (
    docs_config,
    create_api_docs,
    create_feature_docs,
    create_architecture_docs,
    create_documentation_file,
    get_documentation_template
)


def create_api_documentation():
    """Interactive creation of API documentation."""
    print("Creating API Documentation")
    print("-" * 30)
    
    filename = input("Enter filename (without .md): ").strip()
    if not filename:
        print("Filename is required")
        return
    
    title = input("Enter API title: ").strip()
    description = input("Enter API description: ").strip()
    method = input("Enter HTTP method (GET, POST, etc.): ").strip().upper()
    endpoint = input("Enter endpoint path: ").strip()
    
    try:
        file_path = create_api_docs(
            filename=filename,
            title=title,
            description=description,
            method=method,
            endpoint=endpoint,
            endpoint_description="Description of this endpoint",
            request_example="{}",
            response_example="{}",
            auth_requirements="JWT token required",
            error_responses="Standard HTTP error responses",
            usage_examples="Coming soon..."
        )
        print(f"✅ API documentation created: {file_path}")
        print(f"📝 Please edit the file to add specific details")
    except Exception as e:
        print(f"❌ Error creating documentation: {e}")


def create_feature_documentation():
    """Interactive creation of feature documentation."""
    print("Creating Feature Documentation")
    print("-" * 32)
    
    filename = input("Enter filename (without .md): ").strip()
    if not filename:
        print("Filename is required")
        return
    
    feature_name = input("Enter feature name: ").strip()
    overview = input("Enter feature overview: ").strip()
    
    try:
        file_path = create_feature_docs(
            filename=filename,
            feature_name=feature_name,
            overview=overview,
            features_list="- Feature 1\n- Feature 2\n- Feature 3",
            usage_instructions="Coming soon...",
            configuration_details="Coming soon...",
            api_reference="Coming soon...",
            examples="Coming soon...",
            troubleshooting="Coming soon..."
        )
        print(f"✅ Feature documentation created: {file_path}")
        print(f"📝 Please edit the file to add specific details")
    except Exception as e:
        print(f"❌ Error creating documentation: {e}")


def create_architecture_documentation():
    """Interactive creation of architecture documentation."""
    print("Creating Architecture Documentation")
    print("-" * 37)
    
    filename = input("Enter filename (without .md): ").strip()
    if not filename:
        print("Filename is required")
        return
    
    system_name = input("Enter system name: ").strip()
    overview = input("Enter system overview: ").strip()
    
    try:
        file_path = create_architecture_docs(
            filename=filename,
            system_name=system_name,
            overview=overview,
            components_list="Coming soon...",
            data_flow_description="Coming soon...",
            security_details="Coming soon...",
            performance_notes="Coming soon...",
            deployment_instructions="Coming soon..."
        )
        print(f"✅ Architecture documentation created: {file_path}")
        print(f"📝 Please edit the file to add specific details")
    except Exception as e:
        print(f"❌ Error creating documentation: {e}")


def create_custom_documentation():
    """Create custom documentation from scratch."""
    print("Creating Custom Documentation")
    print("-" * 31)
    
    filename = input("Enter filename (without .md): ").strip()
    if not filename:
        print("Filename is required")
        return
    
    title = input("Enter document title: ").strip()
    content = f"""# {title}

## Overview
[Provide an overview of this document]

## Content
[Add your content here]

## Examples
[Add examples if applicable]

## References
[Add references if applicable]
"""
    
    try:
        file_path = create_documentation_file(filename, content)
        print(f"✅ Custom documentation created: {file_path}")
        print(f"📝 Please edit the file to add specific content")
    except Exception as e:
        print(f"❌ Error creating documentation: {e}")


def list_existing_docs():
    """List all existing documentation files."""
    print("Existing Documentation Files")
    print("-" * 33)
    
    docs_files = docs_config.list_docs_files()
    if not docs_files:
        print("No documentation files found")
        return
    
    for i, filename in enumerate(sorted(docs_files), 1):
        file_path = docs_config.get_docs_path(filename)
        file_size = file_path.stat().st_size
        print(f"{i:2d}. {filename} ({file_size:,} bytes)")


def show_docs_info():
    """Show information about the documentation system."""
    print("Documentation System Information")
    print("-" * 36)
    print(f"📁 Documentation directory: {docs_config.docs_dir}")
    print(f"🔧 Auto-generate enabled: {docs_config.auto_generate}")
    print(f"📄 Total documentation files: {len(docs_config.list_docs_files())}")
    print(f"✅ Documentation directory exists: {docs_config.docs_dir.exists()}")


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(
        description="Create and manage project documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/create_docs.py --api       # Create API documentation
  python scripts/create_docs.py --feature   # Create feature documentation
  python scripts/create_docs.py --arch      # Create architecture documentation
  python scripts/create_docs.py --custom    # Create custom documentation
  python scripts/create_docs.py --list      # List existing documentation
  python scripts/create_docs.py --info      # Show documentation system info
        """
    )
    
    parser.add_argument('--api', action='store_true', help='Create API documentation')
    parser.add_argument('--feature', action='store_true', help='Create feature documentation')
    parser.add_argument('--arch', action='store_true', help='Create architecture documentation')
    parser.add_argument('--custom', action='store_true', help='Create custom documentation')
    parser.add_argument('--list', action='store_true', help='List existing documentation')
    parser.add_argument('--info', action='store_true', help='Show documentation system info')
    
    args = parser.parse_args()
    
    # Ensure docs directory exists
    docs_config.ensure_docs_dir_exists()
    
    if args.api:
        create_api_documentation()
    elif args.feature:
        create_feature_documentation()
    elif args.arch:
        create_architecture_documentation()
    elif args.custom:
        create_custom_documentation()
    elif args.list:
        list_existing_docs()
    elif args.info:
        show_docs_info()
    else:
        print("🚀 Speed Dating Documentation Creator")
        print("=" * 38)
        print()
        print("Choose documentation type:")
        print("1. API Documentation")
        print("2. Feature Documentation")
        print("3. Architecture Documentation")
        print("4. Custom Documentation")
        print("5. List Existing Documentation")
        print("6. Documentation System Info")
        print("0. Exit")
        print()
        
        while True:
            choice = input("Enter choice (0-6): ").strip()
            
            if choice == '0':
                print("👋 Goodbye!")
                break
            elif choice == '1':
                create_api_documentation()
                break
            elif choice == '2':
                create_feature_documentation()
                break
            elif choice == '3':
                create_architecture_documentation()
                break
            elif choice == '4':
                create_custom_documentation()
                break
            elif choice == '5':
                list_existing_docs()
                break
            elif choice == '6':
                show_docs_info()
                break
            else:
                print("Invalid choice. Please enter 0-6.")


if __name__ == "__main__":
    main()