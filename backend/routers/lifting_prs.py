from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from database import get_supabase_client

router = APIRouter(prefix="/users/{user_id}/lifting-prs", tags=["lifting_prs"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class LiftingPRCreate(BaseModel):
    exercise_name: str          # e.g. "Press de banca"
    exercise_emoji: str         # e.g. "🏋️"
    weight_kg: float
    reps: Optional[int] = 1    # Default 1 rep max
    pr_date: Optional[date] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/")
def get_lifting_prs(user_id: str):
    """Return all personal records for a user."""
    db = get_supabase_client()
    res = (
        db.table("lifting_prs")
        .select("*")
        .eq("user_id", user_id)
        .order("pr_date", desc=True)
        .execute()
    )
    return res.data or []


@router.post("/")
def upsert_lifting_pr(user_id: str, body: LiftingPRCreate):
    """Create or update a personal record. Updates if weight is heavier than existing PR."""
    db = get_supabase_client()

    # Check if a PR exists for this exercise
    existing = (
        db.table("lifting_prs")
        .select("id, weight_kg")
        .eq("user_id", user_id)
        .eq("exercise_name", body.exercise_name)
        .single()
        .execute()
    )

    payload = {
        "user_id": user_id,
        "exercise_name": body.exercise_name,
        "exercise_emoji": body.exercise_emoji,
        "weight_kg": body.weight_kg,
        "reps": body.reps,
        "pr_date": body.pr_date.isoformat() if body.pr_date else date.today().isoformat(),
    }

    if existing.data:
        if body.weight_kg <= existing.data["weight_kg"]:
            raise HTTPException(
                status_code=409,
                detail=f"New weight ({body.weight_kg} kg) is not heavier than current PR ({existing.data['weight_kg']} kg)"
            )
        # Update existing PR
        res = db.table("lifting_prs").update(payload).eq("id", existing.data["id"]).execute()
        is_new = False
    else:
        # Insert new PR
        res = db.table("lifting_prs").insert(payload).execute()
        is_new = True

    if not res.data:
        raise HTTPException(status_code=400, detail="Could not save PR")

    # Award XP for new PR (+100 XP)
    xp_awarded = 100
    xp_res = db.table("users").select("total_xp").eq("id", user_id).single().execute()
    if xp_res.data:
        new_xp = xp_res.data["total_xp"] + xp_awarded
        db.table("users").update({"total_xp": new_xp}).eq("id", user_id).execute()

    return {"pr": res.data[0], "is_new_record": is_new, "xp_awarded": xp_awarded}
