#!/usr/bin/env python3
"""
Script to fix datetime.utcnow() deprecation warnings across all Python files.

Updates datetime.utcnow() to datetime.now(timezone.utc) and ensures timezone import.
"""

import os
import re
from pathlib import Path


def fix_file(file_path: Path) -> bool:
    """Fix datetime deprecation warnings in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Check if file contains datetime.utcnow()
        if 'datetime.utcnow()' not in content:
            return False
        
        print(f"🔧 Fixing {file_path}")
        
        # Add timezone import if needed
        if 'from datetime import' in content and 'timezone' not in content:
            # Find the datetime import line and add timezone
            content = re.sub(
                r'from datetime import ([^;\n]*)',
                lambda m: f'from datetime import {m.group(1).strip()}, timezone',
                content
            )
        
        # Replace datetime.utcnow() with datetime.now(timezone.utc)
        content = content.replace('datetime.utcnow()', 'datetime.now(timezone.utc)')
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}")
        return False


def main():
    """Fix datetime deprecation warnings in all Python files."""
    print("🔍 Finding Python files with datetime.utcnow() deprecation warnings...")
    
    project_root = Path(__file__).parent
    app_dir = project_root / "app"
    
    # Find all Python files in the app directory
    python_files = list(app_dir.rglob("*.py"))
    
    # Also check test files
    test_files = [f for f in project_root.glob("test_*.py")]
    python_files.extend(test_files)
    
    fixed_count = 0
    total_checked = 0
    
    for file_path in python_files:
        total_checked += 1
        if fix_file(file_path):
            fixed_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   Files checked: {total_checked}")
    print(f"   Files fixed: {fixed_count}")
    
    if fixed_count > 0:
        print(f"\n✅ Fixed datetime.utcnow() deprecation warnings in {fixed_count} files")
    else:
        print(f"\n✅ No files needed fixing")


if __name__ == "__main__":
    main()