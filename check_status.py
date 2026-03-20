#!/usr/bin/env python3
"""
Check Firewatch status and configuration.

Verifies:
- Environment variables
- Database state
- Campground data
- Recent watches
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import sqlite3

load_dotenv()

print("=" * 50)
print("Firewatch Status Check")
print("=" * 50)
print()

# Environment Variables
print("📝 Environment Variables:")
env_vars = {
    'SMTP_HOST': os.getenv('SMTP_HOST'),
    'SMTP_PORT': os.getenv('SMTP_PORT'),
    'SMTP_USER': os.getenv('SMTP_USER'),
    'SMTP_PASSWORD': '***' if os.getenv('SMTP_PASSWORD') else None,
    'API_KEY': '***' if os.getenv('API_KEY') else '(not set - dev mode)',
    'POLL_INTERVAL_MINUTES': os.getenv('POLL_INTERVAL_MINUTES', '5'),
}

for key, value in env_vars.items():
    status = "✓" if value else "✗"
    print(f"  {status} {key}: {value or '(not set)'}")

print()

# Database
print("📊 Database:")
db_path = Path('firewatch.db')
if db_path.exists():
    print(f"  ✓ Database exists: {db_path}")
    
    conn = sqlite3.connect('firewatch.db')
    cursor = conn.cursor()
    
    # Count campgrounds
    cursor.execute("SELECT COUNT(*) FROM campgrounds")
    campground_count = cursor.fetchone()[0]
    print(f"  ✓ Campgrounds: {campground_count}")
    
    # Count watches
    cursor.execute("SELECT COUNT(*) FROM watches")
    watch_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM watches WHERE active = 1")
    active_count = cursor.fetchone()[0]
    print(f"  ✓ Watches: {watch_count} total, {active_count} active")
    
    # Recent watches
    if watch_count > 0:
        print()
        print("  Recent watches:")
        cursor.execute("""
            SELECT campground_name, checkin_date, checkout_date, active, alerted
            FROM watches
            ORDER BY created_at DESC
            LIMIT 5
        """)
        for row in cursor.fetchall():
            status = "Sites Found" if row[4] else ("Active" if row[3] else "Paused")
            print(f"    - {row[0]}: {row[1]} to {row[2]} ({status})")
    
    conn.close()
else:
    print(f"  ✗ Database not found: {db_path}")
    print("    Run: python import_campgrounds.py")

print()

# Configuration Status
print("⚙️  Configuration:")
issues = []

if not os.getenv('SMTP_HOST'):
    issues.append("SMTP_HOST not set")
if not os.getenv('SMTP_USER'):
    issues.append("SMTP_USER not set")
if not os.getenv('SMTP_PASSWORD'):
    issues.append("SMTP_PASSWORD not set")

if campground_count == 0:
    issues.append("No campgrounds imported")

if issues:
    print("  ⚠️  Issues found:")
    for issue in issues:
        print(f"    - {issue}")
else:
    print("  ✓ All required configuration present")

print()
print("=" * 50)

if issues:
    print("⚠️  Fix issues above before testing")
    print("Run: ./setup_testing.sh")
    sys.exit(1)
else:
    print("✓ Ready for testing!")
    print("Run: uvicorn main:app --reload")
