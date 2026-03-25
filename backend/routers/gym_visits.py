from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from database import get_supabase_client

router = APIRouter(prefix="/users/{user_id}/gym-visits", tags=["gym_visits"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class GymVisitCreate(BaseModel):
    gym_name: str
    gym_address: Optional[str] = None
    gym_lat: Optional[float] = None
    gym_lon: Optional[float] = None
    visited_at: Optional[date] = None   # Defaults to today in DB


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
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


@router.post("")
def create_gym_visit(user_id: str, body: GymVisitCreate):
    """Register a gym visit and award XP to the user (+50 XP per visit)."""
    db = get_supabase_client()

    today = date.today()

    # 1. Comprobar si ya existe
    existing = (
        db.table("gym_visits")
        .select("id")
        .eq("user_id", user_id)
        .eq("gym_name", body.gym_name)
        .eq("visited_at", today.isoformat())
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=400, detail="Ya has marcado este centro como visitado hoy.")

    # 2. Insertar nueva visita
    payload = {
        "user_id": user_id,
        "gym_name": body.gym_name,
        "gym_address": body.gym_address,
        "gym_lat": body.gym_lat,
        "gym_lon": body.gym_lon,
    }
    if body.visited_at:
        payload["visited_at"] = body.visited_at.isoformat()

    try:
        res = db.table("gym_visits").insert(payload).execute()
        
        # En Supabase Python v2 as veces insert() no devuelve data según configuración de RLS o Prefer headers.
        # Si no crashea, asumimos éxito.
        visit_record = res.data[0] if res.data else payload
    except Exception as e:
        print(f"Error inserting gym visit: {e}")
        raise HTTPException(status_code=500, detail=f"No se pudo registrar la visita: {str(e)}")

    # Award XP for the visit
    xp_res = db.table("users").select("total_xp").eq("id", user_id).single().execute()
    if xp_res.data:
        new_xp = xp_res.data["total_xp"] + 50
        db.table("users").update({"total_xp": new_xp}).eq("id", user_id).execute()

    return {"visit": visit_record, "xp_awarded": 50}


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

    # Aggregate by gym name with last visit date
    gym_stats = {}
    for v in visits:
        name = v["gym_name"]
        if name not in gym_stats:
            gym_stats[name] = {"visits": 0, "last_visit": v["visited_at"]}
        gym_stats[name]["visits"] += 1
        curr_visited = v.get("visited_at")
        last_visited = gym_stats[name]["last_visit"]
        if curr_visited and (not last_visited or curr_visited > last_visited):
            gym_stats[name]["last_visit"] = curr_visited

    top_gyms = [
        {"gym_name": name, "visits": data["visits"], "last_visit": data["last_visit"]}
        for name, data in sorted(gym_stats.items(), key=lambda item: item[1]["visits"], reverse=True)[:10]
    ]

    return {
        "total_visits": len(visits),
        "unique_gyms": len(gym_stats),
        "top_gyms": top_gyms,
    }
