"""
Import all campgrounds from Recreation.gov into local database.

Run with: python import_campgrounds.py
"""

import httpx
import time
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Campground, Base
from datetime import datetime

USER_AGENT = "Firewatch/1.0 (personal use)"
SEARCH_URL = "https://www.recreation.gov/api/search"


def fetch_all_campgrounds():
    """
    Fetch all campgrounds from Recreation.gov.
    
    Uses search API with pagination to get complete list.
    """
    client = httpx.Client(timeout=30.0)
    campgrounds = []
    offset = 0
    limit = 50
    
    print("Fetching campgrounds from Recreation.gov...")
    
    # Search with wildcard to get all campgrounds
    # We'll iterate through the alphabet to get comprehensive results
    search_terms = [
        "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
        "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
        "camp", "campground", "rv", "tent", "national", "state", "forest"
    ]
    
    seen_ids = set()
    
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
                    
                    campground = {
                        "recreation_id": campground_id,
                        "name": item.get("name", "Unknown"),
                        "city": item.get("city"),
                        "state": item.get("state_code"),
                        "latitude": lat_int,
                        "longitude": lon_int,
                        "preview_image_url": item.get("preview_image_url"),
                        "description": item.get("description"),
                    }
                    
                    campgrounds.append(campground)
                
                print(f"  Found {new_count} new campgrounds (total: {len(campgrounds)})")
                
                # Check if there are more results
                total = data.get("total", 0)
                if offset + limit >= total:
                    break
                
                offset += limit
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"  Error fetching: {e}")
                break
    
    client.close()
    
    print(f"\nTotal unique campgrounds found: {len(campgrounds)}")
    return campgrounds


def import_to_database(campgrounds):
    """Import campgrounds into local database."""
    db = SessionLocal()
    
    try:
        # Create tables if needed
        Base.metadata.create_all(bind=engine)
        
        # Clear existing data
        print("Clearing existing campgrounds...")
        db.query(Campground).delete()
        db.commit()
        
        # Batch insert
        print("Importing campgrounds...")
        batch_size = 100
        
        for i in range(0, len(campgrounds), batch_size):
            batch = campgrounds[i:i+batch_size]
            
            for data in batch:
                campground = Campground(**data, last_synced=datetime.utcnow())
                db.add(campground)
            
            db.commit()
            print(f"  Imported {min(i+batch_size, len(campgrounds))}/{len(campgrounds)}")
        
        print(f"\n✓ Successfully imported {len(campgrounds)} campgrounds")
        
        # Test FTS search
        print("\nTesting FTS search...")
        result = db.execute("""
            SELECT c.recreation_id, c.name, c.city, c.state
            FROM campgrounds_fts f
            JOIN campgrounds c ON f.rowid = c.id
            WHERE campgrounds_fts MATCH 'yosemite'
            LIMIT 5
        """).fetchall()
        
        print(f"Search for 'yosemite' returned {len(result)} results:")
        for row in result:
            print(f"  - {row[1]} ({row[2]}, {row[3]})")
        
    except Exception as e:
        print(f"Error importing: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=== Firewatch Campground Import ===\n")
    
    # Fetch campgrounds
    campgrounds = fetch_all_campgrounds()
    
    if not campgrounds:
        print("No campgrounds found!")
        exit(1)
    
    # Import to database
    import_to_database(campgrounds)
    
    print("\n✓ Import complete!")
