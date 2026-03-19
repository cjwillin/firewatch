"""
Alert dispatching for Firewatch.

Handles:
- Email via SMTP with 3-retry logic (from eng review)
- Pushover notifications (optional, non-blocking)
- Alert content includes booking links (CEO expansion)
- Duration tracking info (CEO expansion)
"""

import smtplib
import httpx
import logging
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import os

logger = logging.getLogger(__name__)


def send_email(
    to: str,
    subject: str,
    body: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    max_retries: int = 3,
) -> bool:
    """
    Send email via SMTP with retry logic.

    Returns True if email sent successfully, False otherwise.

    Retry strategy (from eng review):
    - SMTP timeout → retry 3x with 30s delay
    - SMTP auth failure → fail immediately (config error)
    - SMTP recipient refused → fail immediately (invalid email)

    F-004: Uses STARTTLS on port 587 by default (not SMTP_SSL on 465)
    """
    for attempt in range(max_retries):
        try:
            # F-004: STARTTLS for port 587 (default)
            if smtp_port == 587:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                server.starttls()
            elif smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)

            server.login(smtp_user, smtp_password)

            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent successfully to {to}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            # Auth failure - don't retry, this is a configuration error
            logger.error(f"SMTP authentication failed: {e}. Check SMTP_USER and SMTP_PASSWORD in .env")
            return False

        except smtplib.SMTPRecipientsRefused as e:
            # Invalid recipient - don't retry
            logger.error(f"SMTP recipient refused: {e}. Check alert_email in watch configuration")
            return False

        except (smtplib.SMTPServerDisconnected, OSError, TimeoutError) as e:
            # Transient errors - retry with delay
            logger.warning(f"SMTP error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(30)  # 30 second delay between retries
                continue
            else:
                logger.error(f"Email delivery failed after {max_retries} attempts")
                return False

        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error sending email: {e}")
            return False

    return False


def send_pushover(user_key: str, message: str, title: Optional[str] = None) -> bool:
    """
    Send Pushover notification.

    Returns True if sent successfully, False otherwise.

    No retry logic - Pushover is optional/non-blocking (from eng review).
    """
    app_token = os.getenv("PUSHOVER_APP_TOKEN")
    if not app_token:
        logger.warning("PUSHOVER_APP_TOKEN not configured, skipping Pushover notification")
        return False

    try:
        client = httpx.Client(timeout=10.0)
        response = client.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": app_token,
                "user": user_key,
                "message": message,
                "title": title or "Firewatch Alert",
            }
        )

        if response.status_code == 200:
            logger.info("Pushover notification sent successfully")
            return True
        else:
            logger.warning(f"Pushover API returned {response.status_code}: {response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"Pushover notification failed: {e}")
        return False
    finally:
        client.close()


def format_alert_email(
    campground_name: str,
    checkin_date: str,
    checkout_date: str,
    available_sites: list,
    booking_url: str,
    duration_minutes: Optional[int] = None,
) -> tuple[str, str]:
    """
    Format alert email subject and body.

    Includes:
    - Booking link (CEO expansion)
    - Duration info if available (CEO expansion)
    """
    subject = f"Firewatch: Campsite Available at {campground_name}"

    body = f"""Good news! Campsites are available at {campground_name}.

Dates: {checkin_date} to {checkout_date}

Available Sites:
"""

    for site in available_sites:
        body += f"  - {site['site_name']} ({site['site_type']})\n"

    if duration_minutes is not None:
        body += f"\nThis availability has been open for {duration_minutes} minutes.\n"

    body += f"""
Book now: {booking_url}

---
Firewatch - Your campsite availability monitor
This is an automated alert. To stop receiving alerts for this watch, log in and pause or delete it.
"""

    return subject, body
