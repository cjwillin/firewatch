"""
Campground search endpoints for Firewatch.

Routes:
- GET /api/campgrounds/search - Search campgrounds by name (autocomplete)
"""

from fastapi import APIRouter
import httpx
import logging

router = APIRouter(prefix="/api/campgrounds", tags=["campgrounds"])
logger = logging.getLogger(__name__)


@router.get("/search")
def search_campgrounds(q: str, limit: int = 10):
    """
    Search for campgrounds by name (autocomplete endpoint).

    Query params:
    - q: Search query (min 2 characters)
    - limit: Max results (default 10, max 25)

    Returns: [{"id": "232447", "name": "Yosemite Valley", "location": "CA"}, ...]
    """
    if not q or len(q) < 2:
        return []

    # Cap limit at 25
    limit = min(limit, 25)

    try:
        # Use Recreation.gov's suggest API
        url = f"https://www.recreation.gov/api/search/suggest?q={q}&fq=entity_type:campground"
        headers = {"User-Agent": "Firewatch/1.0 (personal use)"}

        response = httpx.get(url, headers=headers, timeout=5.0)

        if response.status_code != 200:
            return []

        data = response.json()
        suggestions = data.get("inventory_suggestions", [])

        # Filter to campgrounds only and format results
        results = []
        for item in suggestions:
            if item.get("entity_type") == "campground":
                results.append({
                    "id": str(item.get("entity_id", "")),
                    "name": item.get("name", "Unknown"),
                    "location": f"{item.get('city', '')}, {item.get('state_code', '')}".strip(", ")
                })

                if len(results) >= limit:
                    break

        return results

    except Exception as e:
        # Log error but don't crash - just return empty results
        logger.error(f"Campground search failed: {e}")
        return []
