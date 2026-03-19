"""
Campground search and availability endpoints.

Routes:
- GET /api/campgrounds/search - FTS search
- GET /api/campgrounds/{id}/availability - Real-time availability calendar
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models import Campground
from recreation import RecreationClient
from datetime import date
from typing import Optional
import logging

router = APIRouter(prefix="/api/campgrounds", tags=["campgrounds"])
logger = logging.getLogger(__name__)


@router.get("/search")
def search_campgrounds(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=10, le=25),
    db: Session = Depends(get_db)
):
    """
    Fast FTS search for campgrounds.
    
    Returns: [{"id": "232447", "name": "...", "location": "...", "preview_image_url": "..."}, ...]
    """
    try:
        # Escape FTS special characters
        search_term = q.replace('"', '""')
        
        # FTS query with prefix matching
        results = db.execute("""
            SELECT c.recreation_id, c.name, c.city, c.state, c.preview_image_url
            FROM campgrounds_fts f
            JOIN campgrounds c ON f.rowid = c.id
            WHERE campgrounds_fts MATCH :search
            ORDER BY rank
            LIMIT :limit
        """, {"search": f'"{search_term}"*', "limit": limit}).fetchall()
        
        # Format results
        formatted = []
        for row in results:
            location = f"{row[2] or ''}, {row[3] or ''}".strip(", ")
            formatted.append({
                "id": row[0],
                "name": row[1],
                "location": location if location else "Unknown",
                "preview_image_url": row[4]
            })
        
        return formatted
    
    except Exception as e:
        logger.error(f"Search failed: {e}")
        # Fallback to LIKE query if FTS fails
        try:
            results = db.query(Campground).filter(
                Campground.name.ilike(f"%{q}%")
            ).limit(limit).all()
            
            return [c.to_dict() for c in results]
        except:
            return []


@router.get("/{campground_id}/sites")
def get_campground_sites(
    campground_id: str,
    db: Session = Depends(get_db)
):
    """
    Get list of sites for a campground (for site selection UI).

    Returns: [{"site_id": "42", "site_name": "Site 42", "site_type": "Standard"}, ...]
    """
    # Get campground info
    campground = db.query(Campground).filter(
        Campground.recreation_id == campground_id
    ).first()

    if not campground:
        raise HTTPException(status_code=404, detail="Campground not found")

    client = RecreationClient()

    try:
        # Fetch current month's data to get site list
        from datetime import datetime
        month_start = datetime.now().replace(day=1)
        month_param = month_start.strftime("%Y-%m-%dT00:00:00.000Z")

        url = f"{client.BASE_URL}/api/camps/availability/campground/{campground_id}/month?start_date={month_param}"
        headers = {"User-Agent": client.USER_AGENT}

        data = client._retry_request(url, headers)
        if not data:
            return []

        campsites = data.get("campsites", {})
        if not campsites:
            return []

        # Format site list
        sites = []
        for site_id, site_data in campsites.items():
            sites.append({
                "site_id": site_id,
                "site_name": site_data.get("campsite_name", f"Site {site_id}"),
                "site_type": site_data.get("campsite_type", "Unknown")
            })

        # Sort by site ID (numeric if possible)
        sites.sort(key=lambda s: int(s["site_id"]) if s["site_id"].isdigit() else s["site_id"])

        return sites

    except Exception as e:
        logger.error(f"Failed to fetch sites for campground {campground_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch site list: {str(e)[:200]}"
        )

    finally:
        client.close()


@router.get("/{campground_id}/availability")
def check_availability(
    campground_id: str,
    checkin: date = Query(..., description="Check-in date (YYYY-MM-DD)"),
    checkout: date = Query(..., description="Check-out date (YYYY-MM-DD)"),
    site_type: Optional[str] = Query(default="Any", description="Site type filter"),
    site_numbers: Optional[str] = Query(default=None, description="Comma-separated site IDs (e.g., '15,23,42')"),
    db: Session = Depends(get_db)
):
    """
    Check real-time availability with date-by-date breakdown.

    Returns:
    {
        "campground": {...},
        "date_range": {"checkin": "...", "checkout": "..."},
        "availability": {
            "2026-07-01": {"status": "available", "sites_count": 5},
            "2026-07-02": {"status": "sold_out", "sites_count": 0},
            ...
        },
        "available_sites": [{...}, ...],
        "booking_url": "...",
        "has_availability": true
    }
    """
    # Validate dates
    if checkout <= checkin:
        raise HTTPException(status_code=400, detail="Checkout must be after checkin")

    # Parse site_numbers if provided
    site_numbers_list = None
    if site_numbers:
        try:
            site_numbers_list = [int(s.strip()) for s in site_numbers.split(',') if s.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid site_numbers format")

    # Get campground info
    campground = db.query(Campground).filter(
        Campground.recreation_id == campground_id
    ).first()

    if not campground:
        raise HTTPException(status_code=404, detail="Campground not found")

    # Check availability
    client = RecreationClient()

    try:
        # Get detailed availability from Recreation.gov
        availability_data = client.check_availability_detailed(
            campground_id=int(campground_id),
            checkin_date=checkin,
            checkout_date=checkout,
            site_type=site_type,
            site_numbers=site_numbers_list
        )

        booking_url = client.get_booking_url(int(campground_id), checkin, checkout)

        return {
            "campground": campground.to_dict(),
            "date_range": {
                "checkin": checkin.isoformat(),
                "checkout": checkout.isoformat()
            },
            "availability": availability_data["availability"],
            "available_sites": availability_data["available_sites"],
            "booking_url": booking_url,
            "has_availability": availability_data["has_availability"]
        }

    except Exception as e:
        logger.error(f"Availability check failed for campground {campground_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check availability: {str(e)[:200]}"
        )

    finally:
        client.close()
