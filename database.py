"""
Database configuration for Firewatch.

SQLite with WAL mode for concurrent reads (F-008 from documented failure modes).
"""

import sys
import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sqlite3

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./firewatch.db")

try:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Allow multiple threads
        pool_pre_ping=True,  # Verify connections before using
    )
except sqlite3.DatabaseError as e:
    print(f"FATAL: Database error: {e}")
    print(f"Check permissions on {DATABASE_URL}")
    print(f"If corrupted, restore from backup or delete firewatch.db and restart")
    sys.exit(1)


# Enable WAL mode for concurrent reads (F-008)
@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, connection_record):
    """Enable Write-Ahead Logging for better concurrency."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


# Create indexes after tables are created
@event.listens_for(engine, "connect")
def create_indexes(dbapi_conn, connection_record):
    """Create performance indexes (from eng review)."""
    cursor = dbapi_conn.cursor()

    # Index for scheduler query: WHERE active=true AND alerted=false
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_watches_active_alerted
        ON watches(active, alerted)
    """)

    # Index for alert log lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alert_log_watch_id
        ON alert_log(watch_id)
    """)

    # Index for availability window lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_availability_window_site
        ON availability_window(campground_id, site_id)
    """)

    # Index for template expansion deduplication
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_watches_campground_dates
        ON watches(campground_id, checkin_date, checkout_date)
    """)

    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for FastAPI routes to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
