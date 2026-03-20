#!/bin/bash
# Firewatch Testing Setup Script

set -e

echo "===================================="
echo "Firewatch Testing Setup"
echo "===================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your Gmail credentials!"
    echo "   1. Get Gmail App Password: https://myaccount.google.com/apppasswords"
    echo "   2. Fill in SMTP_USER and SMTP_PASSWORD in .env"
    echo ""
    echo "Press Enter after you've updated .env..."
    read -r
else
    echo "✓ .env file exists"
fi

# Check if database exists
if [ ! -f firewatch.db ]; then
    echo ""
    echo "📊 Database not found. It will be created on first run."
fi

# Check if campgrounds are imported
echo ""
echo "🏕️  Checking campground database..."
if [ -f firewatch.db ]; then
    COUNT=$(sqlite3 firewatch.db "SELECT COUNT(*) FROM campgrounds;" 2>/dev/null || echo "0")
    if [ "$COUNT" -gt "0" ]; then
        echo "✓ $COUNT campgrounds in database"
    else
        echo "⚠️  No campgrounds found. Running import..."
        python import_campgrounds.py
    fi
else
    echo "ℹ️  Database will be created and populated on first run"
fi

# Test email
echo ""
echo "📧 Testing email configuration..."
echo "Enter your email address to send a test email:"
read -r EMAIL

if [ -n "$EMAIL" ]; then
    python test_email.py "$EMAIL" && echo "✓ Email test passed!" || echo "✗ Email test failed - check SMTP settings in .env"
fi

echo ""
echo "===================================="
echo "Setup Complete!"
echo "===================================="
echo ""
echo "Next steps:"
echo "1. Start the server:"
echo "   uvicorn main:app --reload"
echo ""
echo "2. Open in browser:"
echo "   http://localhost:8000"
echo ""
echo "3. Follow the testing checklist in TESTING.md"
echo ""
echo "To deploy to production:"
echo "   fly secrets set SMTP_HOST=smtp.gmail.com"
echo "   fly secrets set SMTP_PORT=587"
echo "   fly secrets set SMTP_USER=your-email@gmail.com"
echo "   fly secrets set SMTP_PASSWORD=your-app-password"
echo "   fly deploy"
echo ""
