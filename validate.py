#!/usr/bin/env python3
"""
Firewatch validation script.

Checks that all components import correctly and configuration is valid.
"""

import sys
import os

def check_import(module_name):
    """Try importing a module and return success status."""
    try:
        __import__(module_name)
        return True, None
    except Exception as e:
        return False, str(e)

def main():
    """Run all validation checks."""
    print("🔥 Firewatch Validation Script\n")

    checks = [
        ("Database", "database"),
        ("Models", "models"),
        ("Schemas", "schemas"),
        ("Recreation API", "recreation"),
        ("Alerts", "alerts"),
        ("Scheduler", "scheduler"),
        ("Main App", "main"),
        ("Watch Router", "routers.watches"),
        ("Template Router", "routers.templates"),
        ("Admin Router", "routers.admin"),
    ]

    passed = 0
    failed = 0

    for name, module in checks:
        success, error = check_import(module)
        if success:
            print(f"✅ {name:20} OK")
            passed += 1
        else:
            print(f"❌ {name:20} FAIL: {error}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Total: {passed + failed} checks")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")

    if failed == 0:
        print("\n✅ All validation checks passed!")
        print("   Ready to run: uvicorn main:app --host 0.0.0.0 --port 8000")
        return 0
    else:
        print("\n❌ Some checks failed. Fix errors before running.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
