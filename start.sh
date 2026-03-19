#!/bin/bash

# Firewatch startup script

echo "🔥 Starting Firewatch..."

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run: python3.11 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copying .env.example..."
    cp .env.example .env
    echo "⚠️  Edit .env with your SMTP credentials before running!"
    exit 1
fi

# Check if database exists
if [ ! -f "firewatch.db" ]; then
    echo "📦 Database not found. Running migrations..."
    source venv/bin/activate
    alembic upgrade head
fi

# Activate venv and start
source venv/bin/activate

echo "✅ Starting Firewatch on http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
