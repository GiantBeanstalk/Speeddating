#!/usr/bin/env python3
"""
Simple configuration validation test script.

Tests the settings validation functionality without complex imports.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment to development to avoid production validation errors
os.environ["SPEEDDATING_ENV"] = "development"
os.environ["ENV"] = "development"

try:
    from app.config import settings
    print("✅ Settings module imported successfully")
    
    # Test basic setting access
    secret_key = settings.get("SECRET_KEY")
    database_url = settings.get("DATABASE_URL")
    debug = settings.get("DEBUG")
    
    print(f"   SECRET_KEY: {'*' * len(secret_key) if secret_key else 'Not set'}")
    print(f"   DATABASE_URL: {database_url}")
    print(f"   DEBUG: {debug}")
    
    # Test settings validation
    from app.utils.settings_validator import validate_settings
    print("\n🔍 Running settings validation...")
    
    report = validate_settings()
    
    print(f"\n📊 Validation Results:")
    print(f"   Valid: {report['valid']}")
    print(f"   Errors: {len(report['errors'])}")
    print(f"   Warnings: {len(report['warnings'])}")
    print(f"   Checks passed: {len(report['info'])}")
    
    if report['errors']:
        print(f"\n❌ Errors found:")
        for i, error in enumerate(report['errors'], 1):
            print(f"   {i}. {error}")
    
    if report['warnings']:
        print(f"\n⚠️  Warnings found:")
        for i, warning in enumerate(report['warnings'], 1):
            print(f"   {i}. {warning}")
    
    if report['info']:
        print(f"\n✅ Checks passed:")
        for i, info in enumerate(report['info'][:5], 1):  # Show first 5
            print(f"   {i}. {info}")
        if len(report['info']) > 5:
            print(f"   ... and {len(report['info']) - 5} more")
    
    print(f"\n{report['summary']}")
    
    print("\n" + "=" * 60)
    print("🎉 Configuration validation test completed successfully!")
    
except Exception as e:
    print(f"❌ Error during testing: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)