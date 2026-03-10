from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_supabase_client

router = APIRouter(prefix="/users", tags=["users"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    handle: str
    avatar_url: Optional[str] = None


class UserXPUpdate(BaseModel):
    xp_to_add: int


# ── Helpers ────────────────────────────────────────────────────────────────────

XP_PER_LEVEL = 5000  # XP needed to level up (same as frontend)


def compute_level(total_xp: int) -> tuple[int, int]:
    """Returns (level, xp_within_current_level) from total accumulated XP."""
    level = (total_xp // XP_PER_LEVEL) + 1
    current_xp = total_xp % XP_PER_LEVEL
    return level, current_xp


TITLES = {
    1: "Principiante", 2: "Aprendiz", 3: "Atleta",
    4: "Guerrero", 5: "Campeón", 6: "Élite",
    7: "Maestro", 8: "Gran Maestro", 9: "Leyenda", 10: "FitGod",
}


def get_title(level: int) -> str:
    bucket = min((level - 1) // 3 + 1, 10)
    return TITLES.get(bucket, "FitMaster")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/{user_id}")
def get_user(user_id: str):
    """Get full user profile including computed level, XP and title."""
    db = get_supabase_client()
    res = db.table("users").select("*").eq("id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")

    user = res.data
    level, current_xp = compute_level(user["total_xp"])
    return {
        **user,
        "level": level,
        "current_xp": current_xp,
        "max_xp": XP_PER_LEVEL,
        "xp_percent": round((current_xp / XP_PER_LEVEL) * 100, 1),
        "title": get_title(level),
    }


@router.post("/")
def create_user(body: UserCreate):
    """Create a new user."""
    db = get_supabase_client()
    res = db.table("users").insert({
        "username": body.username,
        "handle": body.handle,
        "avatar_url": body.avatar_url,
        "total_xp": 0,
    }).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Could not create user")
    return res.data[0]


@router.put("/{user_id}/xp")
def add_xp(user_id: str, body: UserXPUpdate):
    """Add XP to a user. Returns updated user with new level info."""
    db = get_supabase_client()

    # Fetch current XP
    res = db.table("users").select("total_xp").eq("id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")

    new_total_xp = res.data["total_xp"] + body.xp_to_add

    # Update in DB
    upd = db.table("users").update({"total_xp": new_total_xp}).eq("id", user_id).execute()
    if not upd.data:
        raise HTTPException(status_code=400, detail="Could not update XP")

    level, current_xp = compute_level(new_total_xp)
    return {
        "user_id": user_id,
        "total_xp": new_total_xp,
        "level": level,
        "current_xp": current_xp,
        "max_xp": XP_PER_LEVEL,
        "title": get_title(level),
    }
