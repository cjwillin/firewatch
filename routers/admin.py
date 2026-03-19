"""
Admin endpoints for Firewatch.

Routes:
- GET /api/health - Health check and system status
- GET /api/logs   - Recent alert logs
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta

from database import get_db
from models import Watch, AlertLog, AvailabilityWindow
from scheduler import get_scheduler

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint.

    Returns system status and statistics:
    - Scheduler status (running/stopped)
    - Watch counts (total, active, alerted)
    - Next check time (if scheduler running)
    - Database status
    - Last alert time
    """
    try:
        # Database check
        watch_count = db.query(Watch).count()
        active_count = db.query(Watch).filter(Watch.active == True).count()
        alerted_count = db.query(Watch).filter(Watch.alerted == True).count()

        # Scheduler check
        scheduler = get_scheduler()
        scheduler_running = scheduler is not None and scheduler.running

        next_run = None
        if scheduler_running:
            job = scheduler.get_job("check_watches")
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()

        # Last alert check
        last_alert = db.query(AlertLog).order_by(AlertLog.triggered_at.desc()).first()
        last_alert_time = last_alert.triggered_at.isoformat() if last_alert else None

        # Availability window stats (CEO expansion)
        window_count = db.query(AvailabilityWindow).count()

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "status": "connected",
                "watches": {
                    "total": watch_count,
                    "active": active_count,
                    "alerted": alerted_count
                },
                "availability_windows": window_count
            },
            "scheduler": {
                "running": scheduler_running,
                "next_check": next_run
            },
            "alerts": {
                "last_sent": last_alert_time
            }
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)[:500]
        }


@router.get("/logs")
def get_logs(
    limit: int = Query(default=50, ge=1, le=500),
    watch_id: int = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Get recent alert logs.

    Query params:
    - limit: Max logs to return (1-500, default 50)
    - watch_id: Filter by specific watch ID (optional)
    - hours: Time window in hours (1-168, default 24)

    Returns logs with watch information joined.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    query = db.query(AlertLog).filter(AlertLog.triggered_at >= cutoff)

    if watch_id:
        query = query.filter(AlertLog.watch_id == watch_id)

    logs = query.order_by(AlertLog.triggered_at.desc()).limit(limit).all()

    # Format response with watch info
    result = []
    for log in logs:
        watch = db.query(Watch).filter(Watch.id == log.watch_id).first()

        result.append({
            "id": log.id,
            "watch_id": log.watch_id,
            "triggered_at": log.triggered_at.isoformat(),
            "message": log.message,
            "watch": {
                "campground_name": watch.campground_name if watch else "Unknown",
                "checkin_date": watch.checkin_date if watch else None,
                "checkout_date": watch.checkout_date if watch else None,
                "alert_email": watch.alert_email if watch else None
            } if watch else None
        })

    return {
        "count": len(result),
        "logs": result,
        "query": {
            "limit": limit,
            "watch_id": watch_id,
            "hours": hours,
            "cutoff": cutoff.isoformat()
        }
    }
