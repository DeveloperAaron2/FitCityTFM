from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from database import get_supabase_client

router = APIRouter(tags=["challenges"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class ChallengeProgressUpdate(BaseModel):
    progress: int   # New progress value (0 to challenge.goal)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/challenges/daily")
def get_daily_challenge():
    """Return the active daily challenge (the one matching today's date or the latest)."""
    db = get_supabase_client()
    today = date.today().isoformat()

    res = (
        db.table("challenges")
        .select("*")
        .eq("active_date", today)
        .single()
        .execute()
    )
    if not res.data:
        # Fallback: return the most recently created challenge
        fallback = (
            db.table("challenges")
            .select("*")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not fallback.data:
            raise HTTPException(status_code=404, detail="No challenge available")
        return fallback.data[0]

    return res.data


@router.get("/challenges/")
def list_challenges():
    """List all available challenges."""
    db = get_supabase_client()
    res = db.table("challenges").select("*").order("active_date", desc=True).execute()
    return res.data or []


@router.get("/users/{user_id}/challenges")
def get_user_challenges(user_id: str):
    """Return all challenges and the user's progress on each."""
    db = get_supabase_client()
    res = (
        db.table("user_challenges")
        .select("*, challenges(*)")
        .eq("user_id", user_id)
        .execute()
    )
    return res.data or []


@router.post("/users/{user_id}/challenges/{challenge_id}/progress")
def update_challenge_progress(user_id: str, challenge_id: str, body: ChallengeProgressUpdate):
    """Update user's progress on a challenge. Marks as completed and awards XP if goal reached."""
    db = get_supabase_client()

    # Get challenge info
    ch_res = db.table("challenges").select("*").eq("id", challenge_id).single().execute()
    if not ch_res.data:
        raise HTTPException(status_code=404, detail="Challenge not found")
    challenge = ch_res.data

    # Get or create user_challenge record
    uc_res = (
        db.table("user_challenges")
        .select("*")
        .eq("user_id", user_id)
        .eq("challenge_id", challenge_id)
        .single()
        .execute()
    )

    completed = body.progress >= challenge["goal"]
    xp_awarded = 0

    if uc_res.data:
        # Update existing
        was_completed = uc_res.data.get("completed", False)
        upd = db.table("user_challenges").update({
            "progress": body.progress,
            "completed": completed,
        }).eq("id", uc_res.data["id"]).execute()
        if not upd.data:
            raise HTTPException(status_code=400, detail="Could not update progress")

        # Award XP only once (first time completing)
        if completed and not was_completed:
            xp_awarded = challenge["xp_reward"]
            xp_res = db.table("users").select("total_xp").eq("id", user_id).single().execute()
            if xp_res.data:
                new_xp = xp_res.data["total_xp"] + xp_awarded
                db.table("users").update({"total_xp": new_xp}).eq("id", user_id).execute()
    else:
        # Insert new
        ins = db.table("user_challenges").insert({
            "user_id": user_id,
            "challenge_id": challenge_id,
            "progress": body.progress,
            "completed": completed,
        }).execute()
        if not ins.data:
            raise HTTPException(status_code=400, detail="Could not create progress record")

        if completed:
            xp_awarded = challenge["xp_reward"]
            xp_res = db.table("users").select("total_xp").eq("id", user_id).single().execute()
            if xp_res.data:
                new_xp = xp_res.data["total_xp"] + xp_awarded
                db.table("users").update({"total_xp": new_xp}).eq("id", user_id).execute()

    return {
        "challenge_id": challenge_id,
        "user_id": user_id,
        "progress": body.progress,
        "goal": challenge["goal"],
        "completed": completed,
        "xp_awarded": xp_awarded,
    }
