#!/usr/bin/env python3
"""
Quick email test script.

Usage:
    python test_email.py your-email@gmail.com

Tests SMTP configuration by sending a test email.
"""

import sys
import os
from dotenv import load_dotenv
from alerts import send_email

# Load .env
load_dotenv()

if len(sys.argv) < 2:
    print("Usage: python test_email.py your-email@gmail.com")
    sys.exit(1)

recipient = sys.argv[1]

print(f"Testing email delivery to {recipient}...")
print(f"SMTP Host: {os.getenv('SMTP_HOST')}")
print(f"SMTP Port: {os.getenv('SMTP_PORT')}")
print(f"SMTP User: {os.getenv('SMTP_USER')}")
print(f"SMTP Password: {'*' * len(os.getenv('SMTP_PASSWORD', ''))}")
print()

result = send_email(
    to=recipient,
    subject="Firewatch Email Test",
    body="""This is a test email from Firewatch.

If you received this, your SMTP configuration is working correctly!

Next steps:
1. Create a watch in the Firewatch UI
2. Wait for the scheduler to run (5 minutes)
3. You'll receive an alert when sites become available

---
Firewatch - Campsite Availability Monitor
""",
    smtp_host=os.getenv('SMTP_HOST'),
    smtp_port=int(os.getenv('SMTP_PORT', 587)),
    smtp_user=os.getenv('SMTP_USER'),
    smtp_password=os.getenv('SMTP_PASSWORD'),
)

if result:
    print("✓ Email sent successfully!")
    print(f"Check your inbox at {recipient}")
else:
    print("✗ Email failed to send")
    print("Check the error messages above for details")
    sys.exit(1)
