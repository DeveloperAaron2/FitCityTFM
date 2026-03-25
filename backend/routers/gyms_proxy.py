import httpx
import logging
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, Query
from urllib.parse import quote

router = APIRouter(prefix="/gyms", tags=["gyms"])
logger = logging.getLogger(__name__)

# Simple in-memory cache targeting "south,west,north,east" boundary bounding boxes
# This ensures instant lookups (0 network overhead) for previously loaded areas.
GYMS_CACHE: Dict[str, Any] = {}
CACHE_LOCK = asyncio.Lock()

import os
import json

# Load static fallback data for 0ms loads
FALLBACK_GYMS = []
fallback_path = os.path.join(os.path.dirname(__file__), "..", "madrid_gyms.json")
try:
    if os.path.exists(fallback_path):
        with open(fallback_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            FALLBACK_GYMS = data.get("elements", [])
        logger.info(f"Loaded {len(FALLBACK_GYMS)} gyms from local fallback.")
except Exception as e:
    logger.error(f"Failed to load fallback gyms: {e}")

def get_fallback_gyms_in_bbox(south: float, west: float, north: float, east: float):
    results = []
    for gym in FALLBACK_GYMS:
        lat = gym.get("lat") or gym.get("center", {}).get("lat")
        lon = gym.get("lon") or gym.get("center", {}).get("lon")
        if lat and lon:
            if south <= lat <= north and west <= lon <= east:
                results.append(gym)
    return results

def build_overpass_query(south: float, west: float, north: float, east: float) -> str:
    bbox = f"{south},{west},{north},{east}"
    return f"""
[out:json][timeout:25];
(
  node["leisure"="fitness_centre"]({bbox});
  node["amenity"="gym"]({bbox});
  node["sport"="fitness"]({bbox});
  way["leisure"="fitness_centre"]({bbox});
  way["amenity"="gym"]({bbox});
  way["leisure"="sports_centre"]["sport"="fitness"]({bbox});
);
out center;
""".strip()

@router.get("/nearby")
async def get_nearby_gyms(
    south: float = Query(..., description="South bounding box"),
    west: float = Query(..., description="West bounding box"),
    north: float = Query(..., description="North bounding box"),
    east: float = Query(..., description="East bounding box"),
):
    """
    Proxies requests to Overpass API and caches the results globally in server RAM.
    This eliminates 504 Gateway errors and prevents IP rate limiting on the client side.
    """
    cache_key = f"{round(south, 3)},{round(west, 3)},{round(north, 3)},{round(east, 3)}"
    
    # 1. Check RAM Cache
    if cache_key in GYMS_CACHE:
        return GYMS_CACHE[cache_key]

    # 2. Check Static Local JSON (Instant 0ms Fallback)
    local_results = get_fallback_gyms_in_bbox(south, west, north, east)
    if len(local_results) > 0:
        logger.info(f"BBOX {cache_key} served from LOCAL JSON ({len(local_results)} gyms).")
        GYMS_CACHE[cache_key] = {"elements": local_results}  # Cache it
        return GYMS_CACHE[cache_key]

    # 3. Fetch from Overpass (Only for unknown areas)
    query = build_overpass_query(south, west, north, east)
    url = f"https://overpass-api.de/api/interpreter?data={quote(query)}"

    async with httpx.AsyncClient() as client:
        retries = 2
        delay_sec = 1.5
        last_err = None
        
        for attempt in range(retries + 1):
            try:
                res = await client.get(url, timeout=12.0)
                res.raise_for_status()
                data = res.json()
                
                # Store in eternal cache
                GYMS_CACHE[cache_key] = data
                logger.info(f"Overpass cache MISS: BBOX {cache_key} fetched and cached.")
                return data
                
            except Exception as e:
                last_err = e
                logger.warning(f"Overpass attempt {attempt + 1} failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(delay_sec * (attempt + 1))
                    
        # Fallback to empty if all fail
        logger.error(f"All overpass retries failed for {cache_key}. Returning empty list. Error: {last_err}")
        return {"elements": []}
