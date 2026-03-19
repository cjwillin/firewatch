"""
Pydantic schemas for Firewatch API.

Uses DRY pattern with WatchConfigBase (from eng review).
"""

from pydantic import BaseModel, validator, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime


class WatchConfigBase(BaseModel):
    """
    Base schema with shared fields between Watch and WatchTemplate.

    DRY pattern from eng review - avoids duplicating 7 fields and validators.
    """
    campground_id: int = Field(..., gt=0, description="Recreation.gov campground ID (must be positive)")
    campground_name: str = Field(..., min_length=1, max_length=200)

    site_type: str = Field(..., description="Standard, Electric, Full Hookup, Group, or Any")
    site_numbers: Optional[List[int]] = Field(None, max_items=50, description="Specific site numbers to watch (max 50)")
    amenity_filters: Optional[Dict[str, Any]] = Field(None, description="Amenity filters (max 10 keys)")

    alert_email: str = Field(..., description="Email for availability alerts")
    pushover_key: Optional[str] = Field(None, max_length=30, description="Pushover user key (optional)")

    @validator('campground_id')
    def validate_campground_id(cls, v):
        """Ensure campground_id is positive integer."""
        if v <= 0:
            raise ValueError('campground_id must be positive')
        return v

    @validator('alert_email')
    def sanitize_email(cls, v):
        """Strip newlines to prevent SMTP header injection (from CEO review security)."""
        return v.replace('\n', '').replace('\r', '').strip()

    @validator('site_numbers')
    def validate_site_numbers(cls, v):
        """Validate site_numbers list."""
        if v is not None:
            if len(v) == 0:
                # Empty list means "no sites match" (from eng review decision)
                return v
            if len(v) > 50:
                raise ValueError('site_numbers cannot exceed 50 items')
            for site_num in v:
                if not isinstance(site_num, int) or site_num <= 0:
                    raise ValueError('site_numbers must be positive integers')
        return v

    @validator('amenity_filters')
    def validate_amenity_filters(cls, v):
        """Validate amenity_filters dict."""
        if v is not None:
            if len(v) > 10:
                raise ValueError('amenity_filters cannot exceed 10 keys')
        return v

    @validator('site_type')
    def validate_site_type(cls, v):
        """Validate site_type is one of allowed values."""
        allowed = ["Standard", "Electric", "Full Hookup", "Group", "Any"]
        if v not in allowed:
            raise ValueError(f'site_type must be one of: {", ".join(allowed)}')
        return v


class WatchCreate(WatchConfigBase):
    """Schema for creating a new watch."""
    checkin_date: date = Field(..., description="Check-in date (ISO format)")
    checkout_date: date = Field(..., description="Check-out date (ISO format, exclusive)")

    @validator('checkout_date')
    def validate_dates(cls, v, values):
        """Ensure checkout_date is after checkin_date."""
        if 'checkin_date' in values and v <= values['checkin_date']:
            raise ValueError('checkout_date must be after checkin_date')
        return v


class WatchUpdate(BaseModel):
    """Schema for updating a watch (partial updates allowed)."""
    active: Optional[bool] = None
    site_numbers: Optional[List[int]] = Field(None, max_items=50)
    amenity_filters: Optional[Dict[str, Any]] = None
    alert_email: Optional[str] = None
    pushover_key: Optional[str] = None

    @validator('alert_email')
    def sanitize_email(cls, v):
        """Strip newlines from email."""
        if v:
            return v.replace('\n', '').replace('\r', '').strip()
        return v


class WatchResponse(BaseModel):
    """Schema for watch API responses."""
    id: int
    campground_id: int
    campground_name: str
    checkin_date: str
    checkout_date: str
    site_type: str
    site_numbers: Optional[List[int]]
    amenity_filters: Optional[Dict[str, Any]]
    alert_email: str
    pushover_key: Optional[str]
    active: bool
    alerted: bool
    last_checked_at: Optional[datetime]
    last_status: Optional[str]
    last_error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2


class WatchTemplateCreate(WatchConfigBase):
    """Schema for creating a watch template."""
    date_range_start: date = Field(..., description="Start date for watch generation")
    date_range_end: date = Field(..., description="End date for watch generation")
    days_of_week: List[int] = Field(..., description="Days of week to generate watches (0=Mon, 6=Sun)")

    @validator('date_range_end')
    def validate_date_range(cls, v, values):
        """Ensure date range is valid and not > 1 year (from CEO review)."""
        if 'date_range_start' in values:
            start = values['date_range_start']
            if v <= start:
                raise ValueError('date_range_end must be after date_range_start')

            # Max 1 year (from CEO review security decision)
            delta = (v - start).days
            if delta > 365:
                raise ValueError('date_range cannot exceed 1 year (365 days)')

        return v

    @validator('days_of_week')
    def validate_days_of_week(cls, v):
        """Validate days_of_week list."""
        if not v:
            # Empty list is allowed (generates 0 watches)
            return v
        for day in v:
            if not isinstance(day, int) or day < 0 or day > 6:
                raise ValueError('days_of_week must be integers 0-6 (0=Monday, 6=Sunday)')
        return v


class WatchTemplateUpdate(BaseModel):
    """Schema for updating a template (partial updates allowed)."""
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    days_of_week: Optional[List[int]] = None
    site_numbers: Optional[List[int]] = Field(None, max_items=50)
    amenity_filters: Optional[Dict[str, Any]] = None
    alert_email: Optional[str] = None
    pushover_key: Optional[str] = None

    @validator('alert_email')
    def sanitize_email(cls, v):
        """Strip newlines from email."""
        if v:
            return v.replace('\n', '').replace('\r', '').strip()
        return v


class WatchTemplateResponse(BaseModel):
    """Schema for template API responses."""
    id: int
    campground_id: int
    campground_name: str
    date_range_start: str
    date_range_end: str
    days_of_week: List[int]
    site_type: str
    site_numbers: Optional[List[int]]
    amenity_filters: Optional[Dict[str, Any]]
    alert_email: str
    pushover_key: Optional[str]
    deleted: bool
    created_at: datetime
    last_expanded_at: Optional[datetime]

    class Config:
        from_attributes = True


class WatchTemplateExpandResponse(BaseModel):
    """Response after template expansion."""
    template_id: int
    watches_created: int  # Count for user visibility (from eng review)


class AlertLogResponse(BaseModel):
    """Schema for alert log entries."""
    id: int
    watch_id: int
    triggered_at: datetime
    message: str

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    """Schema for /health endpoint."""
    healthy: bool  # Computed flag (from eng review)
    last_run: Optional[str]
    next_run: Optional[str]
    active_watch_count: int
    poll_interval_seconds: int
    message: Optional[str]
