"""
Import all campgrounds from Recreation.gov into local database.

Run with: python import_campgrounds.py
"""

import httpx
import time
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import SessionLocal, engine
from models import Campground, Base
from datetime import datetime

USER_AGENT = "Firewatch/1.0 (personal use)"
SEARCH_URL = "https://www.recreation.gov/api/search"


def fetch_and_import_campgrounds(db):
    """
    Fetch all campgrounds from Recreation.gov and import incrementally.

    Uses search API with pagination and commits to DB as we go.
    """
    client = httpx.Client(timeout=30.0)
    total_imported = 0
    offset = 0
    limit = 50

    print("Fetching campgrounds from Recreation.gov...")

    # Get existing IDs to avoid duplicates
    existing_ids = {r[0] for r in db.execute(text("SELECT recreation_id FROM campgrounds")).fetchall()}
    print(f"Database has {len(existing_ids)} existing campgrounds")

    # Search with wildcard to get all campgrounds
    # We'll iterate through the alphabet to get comprehensive results
    search_terms = [
        "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
        "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
        "camp", "campground", "rv", "tent", "national", "state", "forest"
    ]

    seen_ids = set(existing_ids)
    batch = []

    for term in search_terms:
        print(f"Searching for '{term}'...")
        offset = 0

        while True:
            try:
                url = f"{SEARCH_URL}?q={term}&fq=entity_type:campground&start={offset}&size={limit}"
                headers = {"User-Agent": USER_AGENT}

                response = client.get(url, headers=headers)

                if response.status_code != 200:
                    print(f"  Error {response.status_code}, skipping...")
                    break

                data = response.json()
                results = data.get("results", [])

                if not results:
                    break

                new_count = 0
                for item in results:
                    if item.get("entity_type") != "campground":
                        continue

                    campground_id = str(item.get("entity_id", ""))
                    if not campground_id or campground_id in seen_ids:
                        continue

                    seen_ids.add(campground_id)
                    new_count += 1

                    # Extract coordinates and store as integers (x100000)
                    lat = item.get("latitude")
                    lon = item.get("longitude")

                    lat_int = int(float(lat) * 100000) if lat else None
                    lon_int = int(float(lon) * 100000) if lon else None

                    campground = Campground(
                        recreation_id=campground_id,
                        name=item.get("name", "Unknown"),
                        city=item.get("city"),
                        state=item.get("state_code"),
                        latitude=lat_int,
                        longitude=lon_int,
                        preview_image_url=item.get("preview_image_url"),
                        description=item.get("description"),
                        last_synced=datetime.utcnow()
                    )

                    batch.append(campground)

                    # Commit every 50 campgrounds
                    if len(batch) >= 50:
                        db.bulk_save_objects(batch)
                        db.commit()
                        total_imported += len(batch)
                        batch = []

                if new_count > 0:
                    print(f"  Found {new_count} new campgrounds (total: {total_imported + len(batch)})")

                # Check if there are more results
                total = data.get("total", 0)
                if offset + limit >= total:
                    break

                offset += limit
                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                print(f"  Error fetching: {e}")
                break

    # Commit remaining batch
    if batch:
        db.bulk_save_objects(batch)
        db.commit()
        total_imported += len(batch)

    client.close()

    print(f"\nTotal campgrounds imported this run: {total_imported}")
    return total_imported


if __name__ == "__main__":
    print("=== Firewatch Campground Import ===\n")

    db = SessionLocal()

    try:
        # Create tables if needed
        Base.metadata.create_all(bind=engine)

        # Fetch and import incrementally
        total_new = fetch_and_import_campgrounds(db)

        if total_new == 0:
            print("No new campgrounds imported (all already in database)")

        # Test FTS search
        print("\nTesting FTS search...")
        result = db.execute(text("""
            SELECT c.recreation_id, c.name, c.city, c.state
            FROM campgrounds_fts f
            JOIN campgrounds c ON f.rowid = c.id
            WHERE campgrounds_fts MATCH 'yosemite'
            LIMIT 5
        """)).fetchall()

        total_count = db.query(Campground).count()
        print(f"\nTotal campgrounds in database: {total_count}")
        print(f"Search for 'yosemite' returned {len(result)} results:")
        for row in result:
            print(f"  - {row[1]} ({row[2]}, {row[3]})")

        print("\n✓ Import complete!")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
