from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from database import get_supabase_client

router = APIRouter(prefix="/users/{user_id}/gym-visits", tags=["gym_visits"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class GymVisitCreate(BaseModel):
    osm_id: Optional[str] = None        # OpenStreetMap node/way id
    gym_name: str
    gym_address: Optional[str] = None
    gym_lat: Optional[float] = None
    gym_lon: Optional[float] = None
    visited_at: Optional[date] = None   # Defaults to today in DB


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/")
def get_gym_visits(user_id: str):
    """Return all gym visits for a user, ordered by most recent first."""
    db = get_supabase_client()
    res = (
        db.table("gym_visits")
        .select("*")
        .eq("user_id", user_id)
        .order("visited_at", desc=True)
        .execute()
    )
    return res.data or []


@router.post("/")
def create_gym_visit(user_id: str, body: GymVisitCreate):
    """Register a gym visit and award XP to the user (+50 XP per visit)."""
    db = get_supabase_client()

    payload = {
        "user_id": user_id,
        "osm_id": body.osm_id,
        "gym_name": body.gym_name,
        "gym_address": body.gym_address,
        "gym_lat": body.gym_lat,
        "gym_lon": body.gym_lon,
    }
    if body.visited_at:
        payload["visited_at"] = body.visited_at.isoformat()

    res = db.table("gym_visits").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Could not register visit")

    # Award XP for the visit
    xp_res = db.table("users").select("total_xp").eq("id", user_id).single().execute()
    if xp_res.data:
        new_xp = xp_res.data["total_xp"] + 50
        db.table("users").update({"total_xp": new_xp}).eq("id", user_id).execute()

    return {"visit": res.data[0], "xp_awarded": 50}


@router.get("/stats")
def get_gym_visit_stats(user_id: str):
    """Return aggregated gym stats: total visits and top gyms."""
    db = get_supabase_client()
    res = (
        db.table("gym_visits")
        .select("gym_name, gym_address, visited_at")
        .eq("user_id", user_id)
        .execute()
    )
    visits = res.data or []

    # Aggregate by gym name
    from collections import Counter
    counter: Counter = Counter(v["gym_name"] for v in visits)
    top_gyms = [
        {"gym_name": name, "visits": count}
        for name, count in counter.most_common(10)
    ]

    return {
        "total_visits": len(visits),
        "unique_gyms": len(counter),
        "top_gyms": top_gyms,
    }
