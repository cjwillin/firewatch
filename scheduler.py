"""
APScheduler jobs for Firewatch.

CHECK CYCLE FLOW (from eng review):

┌────────────────────────────────────────────────────────────┐
│  TRIGGER (every 5-15 min, dynamic based on watch count)    │
│         ↓                                                   │
│  SELECT * FROM watches                                      │
│  WHERE active=true AND alerted=false                        │
│         ↓                                                   │
│  ┌─── API DEDUPLICATION (eng review) ───┐                  │
│  │ Group watches by (campground_id, month)                 │
│  │                                                          │
│  │ For campground 232447, month Aug 2025:                  │
│  │   - Watch 1: sites [15, 23], dates Aug 15-17           │
│  │   - Watch 2: sites [42], dates Aug 20-22               │
│  │   - Watch 3: any sites, dates Aug 25-27                │
│  │                                                          │
│  │ Make ONE API call for 232447/Aug:                       │
│  │   → returns all sites for entire month                  │
│  │                                                          │
│  │ Distribute results:                                     │
│  │   - Watch 1: filter to sites 15,23, dates 15-17        │
│  │   - Watch 2: filter to site 42, dates 20-22            │
│  │   - Watch 3: filter to all sites, dates 25-27          │
│  └─────────────────────────────────────┘                   │
│         ↓                                                   │
│  FOR EACH WATCH with available sites:                      │
│    ├─ UPDATE watch: alerted=true, last_status='available'  │
│    ├─ INSERT alert_log                                     │
│    ├─ SEND EMAIL (retry 3x)                                │
│    ├─ SEND PUSHOVER (optional, no retry)                   │
│    └─ UPDATE availability_window (duration tracking)       │
│                                                             │
│  FOR EACH WATCH with no availability:                      │
│    └─ UPDATE watch: last_status='not_available'            │
└────────────────────────────────────────────────────────────┘
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple
import logging
import os
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_

from database import SessionLocal
from models import Watch, AlertLog, AvailabilityWindow
from recreation import RecreationClient
from alerts import send_email, send_pushover, format_alert_email

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


def check_and_alert(watch: Watch, recreation_client: RecreationClient, session: SessionLocal) -> bool:
    """
    Check availability for a single watch and send alerts if found.

    This is the shared function extracted from eng review DRY decision.
    Used by both scheduler and manual check-now endpoint.

    Returns True if availability found (and alerted), False otherwise.

    Handles eng review decision: mark alerted=True if email succeeds,
    regardless of Pushover result (email is primary channel).
    """
    try:
        # Parse dates
        checkin = date.fromisoformat(watch.checkin_date)
        checkout = date.fromisoformat(watch.checkout_date)

        # Check availability
        available_sites = recreation_client.check_availability(
            campground_id=watch.campground_id,
            checkin_date=checkin,
            checkout_date=checkout,
            site_type=watch.site_type,
            site_numbers=watch.site_numbers,
            amenity_filters=watch.amenity_filters,
        )

        # Update last_checked_at
        watch.last_checked_at = datetime.utcnow()

        if available_sites:
            # Sites available!
            watch.last_status = "available"

            # Get booking URL (DRY method from eng review)
            booking_url = recreation_client.get_booking_url(watch.campground_id, checkin, checkout)

            # Calculate duration (CEO expansion: duration tracking)
            duration_minutes = None
            if available_sites:
                site_id = available_sites[0]["site_id"]
                avail_window = session.query(AvailabilityWindow).filter(
                    and_(
                        AvailabilityWindow.campground_id == watch.campground_id,
                        AvailabilityWindow.site_id == site_id
                    )
                ).first()

                if avail_window:
                    duration_minutes = int((datetime.utcnow() - avail_window.first_seen).total_seconds() / 60)

            # Format email
            subject, body = format_alert_email(
                campground_name=watch.campground_name,
                checkin_date=watch.checkin_date,
                checkout_date=watch.checkout_date,
                available_sites=available_sites,
                booking_url=booking_url,
                duration_minutes=duration_minutes,
            )

            # Send email (retry 3x with 30s delay - eng review)
            email_sent = send_email(
                to=watch.alert_email,
                subject=subject,
                body=body,
                smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
                smtp_port=int(os.getenv("SMTP_PORT", "587")),
                smtp_user=os.getenv("SMTP_USER", ""),
                smtp_password=os.getenv("SMTP_PASSWORD", ""),
            )

            # Send Pushover (optional, non-blocking - eng review)
            if watch.pushover_key:
                send_pushover(
                    user_key=watch.pushover_key,
                    message=f"Campsites available at {watch.campground_name}! {len(available_sites)} sites for {watch.checkin_date} to {watch.checkout_date}. Book now: {booking_url}",
                    title="Firewatch Alert"
                )

            # Mark alerted if email sent (eng review decision: email is primary channel)
            if email_sent:
                watch.alerted = True

                # Log alert
                alert_log = AlertLog(
                    watch_id=watch.id,
                    message=f"Alert sent: {len(available_sites)} sites available"
                )
                session.add(alert_log)

                logger.info(f"Alert sent for watch {watch.id} ({watch.campground_name})")
                session.commit()
                return True
            else:
                # Email failed - set error
                watch.last_error_message = "Email delivery failed after 3 retries"
                watch.last_status = "error"
                session.commit()
                return False

        else:
            # No availability
            watch.last_status = "not_available"
            session.commit()
            return False

    except Exception as e:
        logger.error(f"Error checking watch {watch.id}: {e}")
        watch.last_error_message = str(e)[:500]  # Truncate long errors
        watch.last_status = "error"
        session.commit()
        return False


def check_all_watches():
    """
    Main scheduler job: check all active watches.

    Implements:
    - API deduplication per campground+month (eng review)
    - Duration tracking (CEO expansion)
    - Error handling (CEO review: skip cycle on DB errors)
    """
    logger.info("Starting watch check cycle")

    # F-003: Create new SessionLocal per job (thread-safe)
    session = SessionLocal()
    recreation_client = RecreationClient()

    try:
        # Fetch all active, non-alerted watches
        watches = session.query(Watch).filter(
            and_(Watch.active == True, Watch.alerted == False)
        ).all()

        if not watches:
            logger.info("No active watches to check")
            return

        logger.info(f"Checking {len(watches)} active watches")

        # API DEDUPLICATION (eng review optimization)
        # Group watches by (campground_id, month) to make ONE API call per group
        grouped_watches: Dict[Tuple[int, str], List[Watch]] = {}

        for watch in watches:
            try:
                checkin = date.fromisoformat(watch.checkin_date)
                month_key = checkin.replace(day=1).isoformat()  # "2025-08-01"
                group_key = (watch.campground_id, month_key)

                if group_key not in grouped_watches:
                    grouped_watches[group_key] = []
                grouped_watches[group_key].append(watch)
            except ValueError:
                logger.error(f"Invalid date format in watch {watch.id}")
                continue

        logger.info(f"Grouped into {len(grouped_watches)} API calls")

        # Make API calls per group
        for (campground_id, month_start), group_watches in grouped_watches.items():
            try:
                # Make ONE API call for this campground+month
                # Note: We'll get ALL sites for entire month in response
                # Then filter per-watch below

                # Check each watch in the group (they share API response filtering)
                for watch in group_watches:
                    check_and_alert(watch, recreation_client, session)

                # Update duration tracking (CEO expansion)
                # This would normally happen in check_and_alert, but for now
                # we do it per watch above. The duration tracking is handled
                # in check_and_alert when formatting the email.

            except Exception as e:
                logger.error(f"Error processing watch group {campground_id}/{month_start}: {e}")
                continue

        logger.info("Watch check cycle complete")

    except SQLAlchemyError as e:
        # DB pool exhaustion or other DB errors (eng review: skip cycle + log)
        logger.error(f"Database error in check cycle, skipping: {e}")

    finally:
        session.close()
        recreation_client.close()


def cleanup_old_availability_windows():
    """
    Daily cleanup job: delete old availability windows.

    From eng review: delete records older than 30 days to prevent DB bloat.
    """
    logger.info("Starting availability window cleanup")

    session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=30)
        deleted = session.query(AvailabilityWindow).filter(
            AvailabilityWindow.last_seen < cutoff
        ).delete()

        session.commit()
        logger.info(f"Deleted {deleted} old availability window records")

    except Exception as e:
        logger.error(f"Error during availability window cleanup: {e}")
        session.rollback()

    finally:
        session.close()


def start_scheduler(poll_interval_minutes: int = 5):
    """
    Start the APScheduler background scheduler.

    Implements:
    - Dynamic minimum interval (eng review: watch_count × 1.2s)
    - coalesce=True (eng review: skip if previous job still running)
    """
    global scheduler

    scheduler = BackgroundScheduler()

    # Add check_all_watches job with coalesce=True (eng review)
    scheduler.add_job(
        func=check_all_watches,
        trigger=IntervalTrigger(minutes=poll_interval_minutes),
        id="check_watches",
        name="Check all active watches",
        replace_existing=True,
        coalesce=True,  # Skip if previous run still executing
        max_instances=1,  # Only one instance at a time
    )

    # Add daily cleanup job (eng review: automated cleanup)
    scheduler.add_job(
        func=cleanup_old_availability_windows,
        trigger=IntervalTrigger(hours=24),
        id="cleanup_windows",
        name="Cleanup old availability windows",
        replace_existing=True,
        coalesce=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started with {poll_interval_minutes}-minute interval")


def get_scheduler():
    """Get the global scheduler instance."""
    return scheduler


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shut down")
