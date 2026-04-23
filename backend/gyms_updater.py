import os
import time
import json
import logging
import asyncio
import httpx
from urllib.parse import quote

# Import the reload function so the app sees new gyms without restarting
from routers.gyms_proxy import load_fallback_gyms, fallback_path

logger = logging.getLogger(__name__)

# Bounding box covering Madrid (approx)
MADRID_BBOX = "40.31,-3.84,40.55,-3.54"

def _build_overpass_query() -> str:
    return f"""
[out:json][timeout:180];
(
  node["leisure"="fitness_centre"]({MADRID_BBOX});
  node["amenity"="gym"]({MADRID_BBOX});
  node["sport"="fitness"]({MADRID_BBOX});
  way["leisure"="fitness_centre"]({MADRID_BBOX});
  way["amenity"="gym"]({MADRID_BBOX});
  way["leisure"="sports_centre"]["sport"="fitness"]({MADRID_BBOX});
);
out center;
""".strip()

async def update_madrid_gyms_if_needed():
    """Check if the JSON is older than 30 days and update it if so."""
    THIRTY_DAYS_SEC = 30 * 24 * 60 * 60

    file_exists = os.path.exists(fallback_path)
    if file_exists:
        mtime = os.path.getmtime(fallback_path)
        age = time.time() - mtime
        if age < THIRTY_DAYS_SEC:
            logger.info(f"madrid_gyms.json is up to date (age: {age/86400:.1f} days).")
            return
        
    logger.info("madrid_gyms.json is older than 30 days. Updating from Overpass API...")
    
    query = _build_overpass_query()
    url = f"https://overpass-api.de/api/interpreter?data={quote(query)}"

    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, timeout=180.0)
            res.raise_for_status()
            data = res.json()
            
            # Save to file
            with open(fallback_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Successfully updated madrid_gyms.json with {len(data.get('elements', []))} gyms.")
            
            # Reload RAM cache
            load_fallback_gyms()
            
    except Exception as e:
        logger.error(f"Failed to update madrid_gyms.json: {e}")

async def monthly_gyms_updater_task():
    """Background task to run the update check repeatedly."""
    while True:
        try:
            await update_madrid_gyms_if_needed()
        except Exception as e:
            logger.error(f"Error in monthly updater task: {e}")
        
        # Check again every 24 hours
        await asyncio.sleep(24 * 60 * 60)
