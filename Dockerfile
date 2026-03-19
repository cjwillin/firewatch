FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for SQLite database
RUN mkdir -p /data

# Set DATABASE_URL to use mounted volume
ENV DATABASE_URL=sqlite:////data/firewatch.db

# Run database migrations on startup
CMD alembic upgrade head && \
    uvicorn main:app --host 0.0.0.0 --port 8000
