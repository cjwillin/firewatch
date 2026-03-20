"""
Recreation.gov API client for Firewatch.

Handles:
- Availability checking with retry logic (F-001 to F-006)
- Site filtering (site_numbers, amenity_filters from CEO expansions)
- Rate limiting (1 req/sec courtesy)
- Exponential backoff on errors

API RESPONSE PARSING FLOW (from eng review):

┌─────────────────────────────────────────────────────────┐
│ GET /api/camps/availability/campground/{id}/month       │
│   ?start_date=2025-08-01T00:00:00.000Z                  │
│         ↓                                                │
│ Response JSON:                                           │
│   {                                                      │
│     "campsites": {                                       │
│       "42": {                                            │
│         "campsite_name": "Site 42",                      │
│         "campsite_type": "STANDARD",                     │
│         "attributes": {                                  │
│           "MaxNumOfPeople": 6,                           │
│           "Driveway Length": 30,                         │
│           "Pets Allowed": "Yes"                          │
│         },                                               │
│         "availabilities": {                              │
│           "2025-08-15T00:00:00Z": "Available",           │
│           "2025-08-16T00:00:00Z": "Available",           │
│           "2025-08-17T00:00:00Z": "Reserved"             │
│         }                                                │
│       },                                                 │
│       "43": { ... }                                      │
│     }                                                    │
│   }                                                      │
│         ↓                                                │
│ FILTER PIPELINE:                                         │
│   1. Extract campsites dict                              │
│   2. For each site:                                      │
│      a. Filter by site_numbers (if specified)           │
│      b. Filter by amenity_filters (if specified)        │
│      c. Filter by date range (checkin to checkout-1)    │
│      d. Check status: "Available" OR "Open" (F-001)     │
│   3. Return list of matching sites                      │
└─────────────────────────────────────────────────────────┘
"""

import httpx
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class RecreationClient:
    """Client for Recreation.gov API."""

    BASE_URL = "https://www.recreation.gov"
    RIDB_URL = "https://ridb.recreation.gov/api/v1"
    USER_AGENT = "Firewatch/1.0 (personal use)"  # F-005: User-Agent required

    def __init__(self):
        self.client = httpx.Client(timeout=10.0)
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce 1 request/second rate limit (courtesy)."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self.last_request_time = time.time()

    def _retry_request(self, url: str, headers: Dict[str, str], max_retries: int = 3) -> Optional[Dict]:
        """
        Make HTTP request with exponential backoff retry.

        Handles:
        - Timeouts → retry 3x
        - 429 rate limit → backoff 2x + retry
        - 500/502/503 → retry 3x
        - Malformed JSON → raise exception
        """
        for attempt in range(max_retries):
            try:
                self._rate_limit()  # Respect 1 req/sec

                response = self.client.get(url, headers=headers)

                # Handle rate limiting (F-002 mentions caching per month, but we do dedup in scheduler)
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                    logger.warning(f"Rate limit 429, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                # Handle server errors
                if response.status_code >= 500:
                    wait_time = (2 ** attempt)  # 1s, 2s, 4s
                    logger.warning(f"Server error {response.status_code}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                # Success
                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception as e:
                        # Malformed JSON (F-001)
                        logger.error(f"Malformed JSON from Recreation.gov: {e}")
                        raise ValueError(f"Invalid JSON response: {e}")

                # Other errors (403, 404, etc)
                logger.error(f"Unexpected status {response.status_code}: {response.text[:200]}")
                return None

            except httpx.TimeoutException:
                wait_time = (2 ** attempt)
                logger.warning(f"Timeout, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                continue

            except httpx.ConnectError as e:
                wait_time = (2 ** attempt)
                logger.error(f"Connection error: {e}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                continue

        # All retries exhausted
        return None

    def get_campground_info(self, campground_id: int) -> Optional[Dict[str, Any]]:
        """
        Get campground details from RIDB API.

        Returns: {name, location, park} or None on error
        """
        url = f"{self.RIDB_URL}/facilities/{campground_id}"
        headers = {"User-Agent": self.USER_AGENT}

        data = self._retry_request(url, headers)
        if not data:
            return None

        return {
            "name": data.get("FacilityName", "Unknown"),
            "location": f"{data.get('FacilityCity', '')}, {data.get('AddressStateCode', '')}",
            "park": data.get("ORGANIZATION", [{}])[0].get("OrgName", ""),
        }

    def check_availability(
        self,
        campground_id: int,
        checkin_date: date,
        checkout_date: date,
        site_type: Optional[str] = None,
        site_numbers: Optional[List[int]] = None,
        amenity_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Check availability for campground and return matching sites.

        Args:
            campground_id: Recreation.gov campground ID
            checkin_date: First night (inclusive)
            checkout_date: Day of departure (exclusive - last night is checkout_date - 1)
            site_type: "Standard", "Electric", "Full Hookup", "Group", or "Any"
            site_numbers: List of specific site numbers to check (filters results)
            amenity_filters: Dict of amenity requirements (filters results)

        Returns:
            List of available sites: [{"site_id": "42", "site_name": "Site 42", ...}, ...]

        Handles F-001 to F-006 documented failure modes.
        """
        # F-002: Availability endpoint takes month start date, not arbitrary ranges
        # We'll fetch the month containing our date range
        month_start = checkin_date.replace(day=1)
        month_param = month_start.strftime("%Y-%m-%dT00:00:00.000Z")

        url = f"{self.BASE_URL}/api/camps/availability/campground/{campground_id}/month?start_date={month_param}"
        headers = {"User-Agent": self.USER_AGENT}

        data = self._retry_request(url, headers)
        if not data:
            return []

        # F-001: Use .get() with defaults, handle schema changes gracefully
        campsites = data.get("campsites", {})
        if not campsites:
            return []

        available_sites = []

        for site_id, site_data in campsites.items():
            # Filter by site_numbers if specified (CEO expansion)
            if site_numbers is not None:
                if len(site_numbers) == 0:
                    # Empty list means "no sites match" (eng review decision)
                    continue
                try:
                    if int(site_id) not in site_numbers:
                        continue
                except ValueError:
                    # Site ID isn't numeric, can't match
                    continue

            # Filter by amenity_filters if specified (CEO expansion)
            if amenity_filters:
                site_attributes = site_data.get("attributes", {})
                matches = True
                for key, value in amenity_filters.items():
                    site_value = site_attributes.get(key)
                    if site_value != value:
                        matches = False
                        break
                if not matches:
                    continue

            # Filter by site_type if not "Any"
            if site_type and site_type != "Any":
                campsite_type = site_data.get("campsite_type", "").upper()
                if site_type.upper().replace(" ", "") not in campsite_type.replace(" ", ""):
                    continue

            # Check availability for our date range
            availabilities = site_data.get("availabilities", {})

            # F-006: Compare date() parts only, not full datetimes
            # checkout_date is EXCLUSIVE (last night is checkout_date - 1)
            has_availability = False
            for avail_date_str, status in availabilities.items():
                try:
                    avail_date = datetime.fromisoformat(avail_date_str.replace("Z", "+00:00")).date()

                    # Check if date is in our range (checkin <= date < checkout)
                    if checkin_date <= avail_date < checkout_date:
                        # F-001: Handle both "Available" and "Open" (loop sites use "Open")
                        if status in ["Available", "Open"]:
                            has_availability = True
                            break
                except (ValueError, AttributeError):
                    continue

            if has_availability:
                available_sites.append({
                    "site_id": site_id,
                    "site_name": site_data.get("campsite_name", f"Site {site_id}"),
                    "site_type": site_data.get("campsite_type", "Unknown"),
                })

        return available_sites

    def check_availability_detailed(
        self,
        campground_id: int,
        checkin_date: date,
        checkout_date: date,
        site_type: Optional[str] = None,
        site_numbers: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Check availability with date-by-date breakdown for calendar UI.

        Returns:
        {
            "availability": {
                "2026-07-01": {"status": "available", "sites_count": 5},
                "2026-07-02": {"status": "sold_out", "sites_count": 0},
                ...
            },
            "available_sites": [{site_id, site_name, site_type, available_dates}, ...],
            "sites_detail": [{site_id, site_name, site_type, loop, attributes, daily_availability}, ...],
            "has_availability": bool
        }
        """
        # Fetch raw data from Recreation.gov
        month_start = checkin_date.replace(day=1)
        month_param = month_start.strftime("%Y-%m-%dT00:00:00.000Z")

        url = f"{self.BASE_URL}/api/camps/availability/campground/{campground_id}/month?start_date={month_param}"
        headers = {"User-Agent": self.USER_AGENT}

        data = self._retry_request(url, headers)
        if not data:
            return {
                "availability": {},
                "available_sites": [],
                "sites_detail": [],
                "has_availability": False
            }

        campsites = data.get("campsites", {})
        if not campsites:
            return {
                "availability": {},
                "available_sites": [],
                "sites_detail": [],
                "has_availability": False
            }

        # Build date-by-date availability map
        date_availability = {}
        available_sites_list = []
        sites_detail = []

        # Initialize all dates in range as sold out
        current_date = checkin_date
        while current_date < checkout_date:
            date_availability[current_date.isoformat()] = {
                "status": "sold_out",
                "sites_count": 0
            }
            current_date += timedelta(days=1)

        # Process each site
        for site_id, site_data in campsites.items():
            # Filter by site_numbers if specified
            if site_numbers is not None:
                if len(site_numbers) == 0:
                    continue
                try:
                    if int(site_id) not in site_numbers:
                        continue
                except ValueError:
                    continue

            # Filter by site_type if not "Any"
            if site_type and site_type != "Any":
                campsite_type = site_data.get("campsite_type", "").upper()
                if site_type.upper().replace(" ", "") not in campsite_type.replace(" ", ""):
                    continue

            availabilities = site_data.get("availabilities", {})
            site_available_dates = []
            daily_availability = {}

            # Check each date in our range
            for avail_date_str, status in availabilities.items():
                try:
                    avail_date = datetime.fromisoformat(avail_date_str.replace("Z", "+00:00")).date()

                    # Only consider dates in our range
                    if checkin_date <= avail_date < checkout_date:
                        date_str = avail_date.isoformat()
                        daily_availability[date_str] = status

                        if status in ["Available", "Open"]:
                            # Update date availability count
                            if date_str in date_availability:
                                date_availability[date_str]["status"] = "available"
                                date_availability[date_str]["sites_count"] += 1

                            site_available_dates.append(date_str)

                except (ValueError, AttributeError):
                    continue

            # Extract site attributes
            attributes = site_data.get("attributes", {})

            # Build detailed site info
            site_detail = {
                "site_id": site_id,
                "site_name": site_data.get("campsite_name", f"Site {site_id}"),
                "site_type": site_data.get("campsite_type", "Unknown"),
                "loop": site_data.get("loop", "Unknown"),
                "attributes": {
                    "max_people": attributes.get("MaxNumOfPeople", attributes.get("Max Num of People", "N/A")),
                    "trailer_length": attributes.get("Max Trailer Length", attributes.get("Driveway Length", "N/A")),
                    "rv_length": attributes.get("Max RV Length", "N/A"),
                    "vehicle_length": attributes.get("Max Vehicle Length", "N/A"),
                    "pets_allowed": attributes.get("Pets Allowed", "N/A"),
                    "tent_allowed": "Yes" if "TENT" in site_data.get("campsite_type", "").upper() else "No",
                    "rv_allowed": "Yes" if "RV" in site_data.get("campsite_type", "").upper() else "No",
                    "has_fire_pit": attributes.get("Campfire Allowed", "N/A"),
                    "has_table": attributes.get("Picnic Table", "N/A"),
                    "has_hookups": attributes.get("Electric Hookup", "N/A"),
                },
                "daily_availability": daily_availability,
                "has_availability": len(site_available_dates) > 0
            }

            sites_detail.append(site_detail)

            # If site has any availability in our range, add it to available_sites summary
            if site_available_dates:
                available_sites_list.append({
                    "site_id": site_id,
                    "site_name": site_data.get("campsite_name", f"Site {site_id}"),
                    "site_type": site_data.get("campsite_type", "Unknown"),
                    "available_dates": site_available_dates
                })

        # Sort sites_detail by site_id (numeric if possible)
        sites_detail.sort(key=lambda s: int(s["site_id"]) if str(s["site_id"]).isdigit() else s["site_id"])

        has_availability = any(
            day["status"] == "available"
            for day in date_availability.values()
        )

        return {
            "availability": date_availability,
            "available_sites": available_sites_list,
            "sites_detail": sites_detail,
            "has_availability": has_availability
        }

    def search_campgrounds(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for campgrounds by name.

        Used for UI autocomplete (CEO expansion: campground search widget).

        Returns: [{"id": 232447, "name": "Yosemite Valley", "location": "..."}, ...]
        """
        url = f"{self.RIDB_URL}/facilities?query={query}&activity=9&limit={limit}"
        headers = {"User-Agent": self.USER_AGENT}

        data = self._retry_request(url, headers)
        if not data or "RECDATA" not in data:
            return []

        results = []
        for facility in data["RECDATA"]:
            results.append({
                "id": facility.get("FacilityID"),
                "name": facility.get("FacilityName", "Unknown"),
                "location": f"{facility.get('FacilityCity', '')}, {facility.get('AddressStateCode', '')}",
            })

        return results

    def get_booking_url(self, campground_id: int, checkin_date: date, checkout_date: date) -> str:
        """
        Construct Recreation.gov booking URL with pre-filled dates.

        Extracted as shared method (eng review DRY decision).

        Used in alert emails (CEO expansion: booking links in alerts).
        """
        checkin_str = checkin_date.isoformat()
        checkout_str = checkout_date.isoformat()
        return f"{self.BASE_URL}/camping/campgrounds/{campground_id}/availability?date={checkin_str}&length={( checkout_date - checkin_date).days}"

    def close(self):
        """Close HTTP client."""
        self.client.close()
