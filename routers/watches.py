"""
Watch CRUD endpoints for Firewatch.

Routes:
- GET    /api/watches          - List all watches
- POST   /api/watches          - Create new watch
- GET    /api/watches/{id}     - Get watch by ID
- PUT    /api/watches/{id}     - Update watch
- DELETE /api/watches/{id}     - Delete watch
- POST   /api/watches/{id}/reset-alert  - Reset alerted flag
- POST   /api/watches/{id}/check-now    - Manual availability check
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from database import get_db
from models import Watch
from schemas import WatchCreate, WatchUpdate, WatchResponse
from recreation import RecreationClient
from scheduler import check_and_alert

router = APIRouter(prefix="/api/watches", tags=["watches"])

# 1000 watch limit (eng review decision)
MAX_WATCHES = 1000


@router.get("", response_model=List[WatchResponse])
def list_watches(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """
    List all watches, optionally filtered by active status.

    Query params:
    - active_only: If true, only return active watches
    """
    query = db.query(Watch)

    if active_only:
        query = query.filter(Watch.active == True)

    watches = query.order_by(Watch.created_at.desc()).all()
    return watches


@router.post("", response_model=WatchResponse, status_code=status.HTTP_201_CREATED)
def create_watch(
    watch_data: WatchCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new watch.

    Enforces 1000 watch limit (eng review decision).
    Prevents duplicate watches via DB unique constraint.
    """
    # Check 1000 watch limit (eng review decision)
    count = db.query(Watch).count()
    if count >= MAX_WATCHES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Watch limit reached ({MAX_WATCHES}). Delete unused watches to create new ones."
        )

    # Create watch
    watch = Watch(**watch_data.dict())

    try:
        db.add(watch)
        db.commit()
        db.refresh(watch)
        return watch

    except Exception as e:
        db.rollback()

        # Check for unique constraint violation (duplicate watch)
        if "UNIQUE constraint failed" in str(e) or "unique_watch" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A watch with this campground, dates, and site type already exists"
            )

        # Other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create watch: {str(e)[:200]}"
        )


@router.get("/{watch_id}", response_model=WatchResponse)
def get_watch(
    watch_id: int,
    db: Session = Depends(get_db)
):
    """Get a single watch by ID."""
    watch = db.query(Watch).filter(Watch.id == watch_id).first()

    if not watch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Watch {watch_id} not found"
        )

    return watch


@router.put("/{watch_id}", response_model=WatchResponse)
def update_watch(
    watch_id: int,
    watch_data: WatchUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a watch.

    Can update any field except created_at.
    Commonly used to pause/unpause (active=false/true).
    """
    watch = db.query(Watch).filter(Watch.id == watch_id).first()

    if not watch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Watch {watch_id} not found"
        )

    # Update fields (exclude unset fields)
    update_data = watch_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(watch, field, value)

    try:
        db.commit()
        db.refresh(watch)
        return watch

    except Exception as e:
        db.rollback()

        # Check for unique constraint violation
        if "UNIQUE constraint failed" in str(e) or "unique_watch" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A watch with this campground, dates, and site type already exists"
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update watch: {str(e)[:200]}"
        )


@router.delete("/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watch(
    watch_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a watch.

    AlertLog entries are cascade-deleted (FK with ondelete=CASCADE).
    """
    watch = db.query(Watch).filter(Watch.id == watch_id).first()

    if not watch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Watch {watch_id} not found"
        )

    try:
        db.delete(watch)
        db.commit()
        return None  # 204 No Content

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete watch: {str(e)[:200]}"
        )


@router.post("/{watch_id}/reset-alert", response_model=WatchResponse)
def reset_alert(
    watch_id: int,
    db: Session = Depends(get_db)
):
    """
    Reset alerted flag to false.

    Used when user wants to receive alerts again for the same availability.
    Clears last_error_message.
    """
    watch = db.query(Watch).filter(Watch.id == watch_id).first()

    if not watch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Watch {watch_id} not found"
        )

    watch.alerted = False
    watch.last_error_message = None
    watch.last_status = None

    try:
        db.commit()
        db.refresh(watch)
        return watch

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset alert: {str(e)[:200]}"
        )


@router.post("/{watch_id}/check-now")
def check_now(
    watch_id: int,
    db: Session = Depends(get_db)
):
    """
    Manually trigger availability check and send alert if available.

    Uses shared check_and_alert() function (eng review DRY decision).

    Returns:
    - {"status": "available", "message": "..."} if sites found and alert sent
    - {"status": "not_available", "message": "..."} if no sites found
    - {"status": "error", "message": "..."} if check failed
    """
    watch = db.query(Watch).filter(Watch.id == watch_id).first()

    if not watch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Watch {watch_id} not found"
        )

    # Use shared function (eng review DRY decision)
    recreation_client = RecreationClient()

    try:
        result = check_and_alert(watch, recreation_client, db)

        # Refresh watch to get updated fields
        db.refresh(watch)

        if result:
            return {
                "status": "available",
                "message": f"Sites available! Alert sent to {watch.alert_email}",
                "watch": watch
            }

        elif watch.last_status == "error":
            return {
                "status": "error",
                "message": watch.last_error_message or "Check failed",
                "watch": watch
            }

        else:
            return {
                "status": "not_available",
                "message": "No sites available",
                "watch": watch
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Check failed: {str(e)[:200]}"
        )

    finally:
        recreation_client.close()
