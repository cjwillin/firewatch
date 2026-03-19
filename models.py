"""
Database models for Firewatch.

Includes ASCII diagrams for state machines and relationships (from eng review).
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from datetime import datetime, date, timedelta
from database import Base


class Watch(Base):
    """
    Campsite availability watch.

    STATE MACHINE (active, alerted, error states):

    ┌──────────────────────────────────────────────────────────┐
    │  CREATE                                                   │
    │    ↓                                                      │
    │  [active=True, alerted=False, last_status=None]          │
    │    ↓                                                      │
    │  ┌─────────── SCHEDULER CHECKS ─────────┐                │
    │  │                                      │                │
    │  │  ┌──── Site Available? ────┐        │                │
    │  │  │         YES    │    NO   │        │                │
    │  │  ↓                ↓         │        │                │
    │  │  alerted=True    last_status│        │                │
    │  │  last_status=    ='not_     │        │                │
    │  │  'available'     available' │        │                │
    │  │  ALERT SENT!                │        │                │
    │  │  │                ↓         │        │                │
    │  │  │         (stays active)   │        │                │
    │  │  │                │         │        │                │
    │  │  └────────────────┴─────────┘        │                │
    │  │            │                         │                │
    │  │            ↓                         │                │
    │  │     ┌─── ERROR? ────┐               │                │
    │  │     │   YES  │  NO   │               │                │
    │  │     ↓        ↓       │               │                │
    │  │   last_error_  (OK)  │               │                │
    │  │   message set        │               │                │
    │  │   last_status=       │               │                │
    │  │   'error'            │               │                │
    │  │     │        │       │               │                │
    │  │     └────────┴───────┘               │                │
    │  └──────────────────────────────────────┘                │
    │                                                           │
    │  USER ACTIONS:                                           │
    │    - DELETE → removed from DB                            │
    │    - PATCH active=False → paused (stops checking)        │
    │    - PATCH active=True → resumed                         │
    │    - POST /reset-alert → alerted=False (check again)     │
    └──────────────────────────────────────────────────────────┘
    """
    __tablename__ = "watches"

    id = Column(Integer, primary_key=True, index=True)
    campground_id = Column(Integer, nullable=False, index=True)
    campground_name = Column(String, nullable=False)

    # Date range (checkout_date is EXCLUSIVE - last night is checkout_date - 1)
    checkin_date = Column(String, nullable=False)  # ISO date: "2025-08-15"
    checkout_date = Column(String, nullable=False)  # ISO date: "2025-08-17"

    # Site filtering (from CEO-accepted expansions)
    site_type = Column(String, nullable=False)  # "Standard", "Electric", "Full Hookup", "Group", "Any"
    site_numbers = Column(JSON, nullable=True)  # List of specific site numbers: [15, 23, 67] or null for "any"
    amenity_filters = Column(JSON, nullable=True)  # Dict of amenity filters: {"rv_length": 30, "pets": true}

    # Alert configuration
    alert_email = Column(String, nullable=False)
    pushover_key = Column(String, nullable=True)

    # State
    active = Column(Boolean, default=True, nullable=False)
    alerted = Column(Boolean, default=False, nullable=False)

    # Status tracking
    last_checked_at = Column(DateTime, nullable=True)
    last_status = Column(String, nullable=True)  # "available", "not_available", "error", None
    last_error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Unique constraint to prevent duplicate watches
    __table_args__ = (
        UniqueConstraint('campground_id', 'checkin_date', 'checkout_date', 'site_type',
                         name='unique_watch'),
    )


class WatchTemplate(Base):
    """
    Template for auto-generating watches across date ranges.

    EXPANSION LOGIC (from CEO-accepted expansions):

    ┌────────────────────────────────────────────────────────────┐
    │  Template Created:                                          │
    │    campground_id: 232447                                    │
    │    date_range_start: 2025-08-01                             │
    │    date_range_end: 2025-08-31                               │
    │    days_of_week: [5, 6]  (Fri=5, Sat=6)                     │
    │    site_type: "Standard"                                    │
    │    site_numbers: [15, 23]                                   │
    │         ↓                                                   │
    │  ┌─── EXPANSION ───┐                                        │
    │  │ 1. Iterate dates from start to end                      │
    │  │ 2. Filter by days_of_week                               │
    │  │ 3. For each matching date:                              │
    │  │    a. Check if Watch exists (DEDUP, from eng review)    │
    │  │       SELECT * FROM watches                             │
    │  │       WHERE campground_id=232447                        │
    │  │         AND checkin_date='2025-08-01'                   │
    │  │         AND checkout_date='2025-08-03'                  │
    │  │         AND site_type='Standard'                        │
    │  │    b. If NOT exists: CREATE Watch                       │
    │  │    c. Copy site_numbers, amenity_filters                │
    │  │       from template to watch                            │
    │  │ 4. Return count of watches created                      │
    │  └─────────────────┘                                        │
    │         ↓                                                   │
    │  Result: 8 watches created (4 Fridays + 4 Saturdays)       │
    │                                                             │
    │  If template deleted: watches persist (soft-delete)         │
    └────────────────────────────────────────────────────────────┘
    """
    __tablename__ = "watch_templates"

    id = Column(Integer, primary_key=True, index=True)
    campground_id = Column(Integer, nullable=False)
    campground_name = Column(String, nullable=False)

    # Date range (max 1 year, validated in schema)
    date_range_start = Column(String, nullable=False)  # ISO date
    date_range_end = Column(String, nullable=False)  # ISO date
    days_of_week = Column(JSON, nullable=False)  # List of integers 0-6 (Mon=0, Sun=6)

    # Site configuration (same as Watch)
    site_type = Column(String, nullable=False)
    site_numbers = Column(JSON, nullable=True)
    amenity_filters = Column(JSON, nullable=True)

    # Alert configuration
    alert_email = Column(String, nullable=False)
    pushover_key = Column(String, nullable=True)

    # Soft-delete flag
    deleted = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_expanded_at = Column(DateTime, nullable=True)


class AlertLog(Base):
    """
    Log of all alerts sent.

    Used for:
    - Alert history display
    - Debugging alert delivery
    - Future: Success rate analytics (deferred to TODOS)
    """
    __tablename__ = "alert_log"

    id = Column(Integer, primary_key=True, index=True)
    watch_id = Column(Integer, ForeignKey("watches.id", ondelete="CASCADE"), nullable=False, index=True)
    triggered_at = Column(DateTime, server_default=func.now(), nullable=False)
    message = Column(Text, nullable=False)


class AvailabilityWindow(Base):
    """
    Tracks when sites first become available and for how long.

    Used for duration display: "Available for 14 minutes"
    (from CEO-accepted expansions)

    DURATION TRACKING LOGIC:

    ┌────────────────────────────────────────────────────────────┐
    │  Scheduler checks availability:                             │
    │                                                             │
    │  IF site is "Available":                                    │
    │    ┌─ Record exists? ─┐                                    │
    │    │   YES      NO     │                                    │
    │    ↓            ↓      │                                    │
    │  UPDATE     CREATE     │                                    │
    │  last_seen  first_seen │                                    │
    │  =now()     =now()     │                                    │
    │             last_seen  │                                    │
    │             =now()     │                                    │
    │    │            │      │                                    │
    │    └────────────┘      │                                    │
    │         ↓              │                                    │
    │  Duration = now() - first_seen                              │
    │  Display: "Available for X minutes"                         │
    │                                                             │
    │  IF site is NOT "Available":                                │
    │    (Do nothing - record stays with last_seen)               │
    │                                                             │
    │  Cleanup job (daily):                                       │
    │    DELETE FROM availability_window                          │
    │    WHERE last_seen < NOW() - 30 days                        │
    └────────────────────────────────────────────────────────────┘
    """
    __tablename__ = "availability_window"

    id = Column(Integer, primary_key=True, index=True)
    campground_id = Column(Integer, nullable=False, index=True)
    site_id = Column(String, nullable=False)  # Recreation.gov site ID (string, e.g., "42")

    first_seen = Column(DateTime, nullable=False)  # When site first became available
    last_seen = Column(DateTime, nullable=False)  # Most recent check showing available

    # duration_seconds is computed as (last_seen - first_seen).total_seconds()
    # Not stored in DB, calculated in application logic
