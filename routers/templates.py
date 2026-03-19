"""
Watch template CRUD endpoints for Firewatch.

Routes:
- GET    /api/templates          - List all templates
- POST   /api/templates          - Create new template
- GET    /api/templates/{id}     - Get template by ID
- PUT    /api/templates/{id}     - Update template
- DELETE /api/templates/{id}     - Soft-delete template
- POST   /api/templates/{id}/expand  - Expand template to watches
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
from datetime import date, timedelta

from database import get_db
from models import WatchTemplate, Watch
from schemas import WatchTemplateCreate, WatchTemplateUpdate, WatchTemplateResponse

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=List[WatchTemplateResponse])
def list_templates(
    include_deleted: bool = False,
    db: Session = Depends(get_db)
):
    """
    List all templates.

    Query params:
    - include_deleted: If true, include soft-deleted templates
    """
    query = db.query(WatchTemplate)

    if not include_deleted:
        query = query.filter(WatchTemplate.deleted == False)

    templates = query.order_by(WatchTemplate.created_at.desc()).all()
    return templates


@router.post("", response_model=WatchTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    template_data: WatchTemplateCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new watch template.

    Does not automatically expand to watches.
    Use POST /api/templates/{id}/expand to generate watches.
    """
    template = WatchTemplate(**template_data.dict())

    try:
        db.add(template)
        db.commit()
        db.refresh(template)
        return template

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create template: {str(e)[:200]}"
        )


@router.get("/{template_id}", response_model=WatchTemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """Get a single template by ID."""
    template = db.query(WatchTemplate).filter(WatchTemplate.id == template_id).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )

    return template


@router.put("/{template_id}", response_model=WatchTemplateResponse)
def update_template(
    template_id: int,
    template_data: WatchTemplateUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a template.

    Does not affect existing watches created from this template.
    """
    template = db.query(WatchTemplate).filter(WatchTemplate.id == template_id).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )

    # Update fields
    update_data = template_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    try:
        db.commit()
        db.refresh(template)
        return template

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update template: {str(e)[:200]}"
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """
    Soft-delete a template.

    Sets deleted=true. Watches created from this template persist.
    """
    template = db.query(WatchTemplate).filter(WatchTemplate.id == template_id).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )

    template.deleted = True

    try:
        db.commit()
        return None  # 204 No Content

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete template: {str(e)[:200]}"
        )


@router.post("/{template_id}/expand")
def expand_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """
    Expand template to watches for all matching dates.

    EXPANSION LOGIC (from CEO-accepted expansion):

    ┌────────────────────────────────────────────────────────────┐
    │  1. Iterate dates from date_range_start to date_range_end  │
    │  2. Filter by days_of_week (e.g., [5, 6] = Fri+Sat)       │
    │  3. For each matching date:                                 │
    │     a. Check if Watch exists (DEDUP, eng review decision)  │
    │        SELECT * FROM watches                                │
    │        WHERE campground_id=X AND checkin_date=Y            │
    │          AND checkout_date=Z AND site_type=T               │
    │     b. If NOT exists: CREATE Watch                         │
    │     c. Copy site_numbers, amenity_filters from template    │
    │  4. Return count of watches created                         │
    └────────────────────────────────────────────────────────────┘

    Returns:
    - {"created": N, "skipped": M, "dates": [...]}
    """
    template = db.query(WatchTemplate).filter(WatchTemplate.id == template_id).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )

    # Parse date range
    try:
        start_date = date.fromisoformat(template.date_range_start)
        end_date = date.fromisoformat(template.date_range_end)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {e}"
        )

    # Iterate dates and create watches
    created_count = 0
    skipped_count = 0
    created_dates = []

    current_date = start_date
    while current_date <= end_date:
        # Check if date's weekday matches template's days_of_week
        # Python weekday(): Mon=0, Sun=6
        if current_date.weekday() in template.days_of_week:
            # Calculate checkout date (assuming 2-night stay, adjust as needed)
            # CEO expansion: use standard 2-night checkout
            checkout_date = current_date + timedelta(days=2)

            # Check if watch already exists (DEDUP, eng review decision)
            existing = db.query(Watch).filter(
                and_(
                    Watch.campground_id == template.campground_id,
                    Watch.checkin_date == current_date.isoformat(),
                    Watch.checkout_date == checkout_date.isoformat(),
                    Watch.site_type == template.site_type
                )
            ).first()

            if not existing:
                # Create watch from template
                watch = Watch(
                    campground_id=template.campground_id,
                    campground_name=template.campground_name,
                    checkin_date=current_date.isoformat(),
                    checkout_date=checkout_date.isoformat(),
                    site_type=template.site_type,
                    site_numbers=template.site_numbers,
                    amenity_filters=template.amenity_filters,
                    alert_email=template.alert_email,
                    pushover_key=template.pushover_key,
                    active=True,
                    alerted=False
                )

                db.add(watch)
                created_count += 1
                created_dates.append(current_date.isoformat())
            else:
                skipped_count += 1

        current_date += timedelta(days=1)

    # Update template's last_expanded_at
    from datetime import datetime
    template.last_expanded_at = datetime.utcnow()

    try:
        db.commit()

        return {
            "created": created_count,
            "skipped": skipped_count,
            "dates": created_dates,
            "message": f"Created {created_count} watches, skipped {skipped_count} duplicates"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template expansion failed: {str(e)[:200]}"
        )
