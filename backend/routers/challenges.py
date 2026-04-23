from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from database import get_supabase_client
from utils import award_xp_and_check_level

router = APIRouter(tags=["challenges"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class ChallengeProgressUpdate(BaseModel):
    progress: int   # New progress value (0 to challenge.goal)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _current_month() -> str:
    """Return current month as 'YYYY-MM'."""
    return date.today().strftime("%Y-%m")


def _count_user_gym_visits_today(db, user_id: str) -> int:
    """Count how many distinct gyms the user visited today."""
    today = date.today().isoformat()
    res = (
        db.table("gym_visits")
        .select("gym_name")
        .eq("user_id", user_id)
        .eq("visited_at", today)
        .execute()
    )
    return len(res.data) if res.data else 0


def _count_user_gym_visits_month(db, user_id: str) -> int:
    """Count distinct days the user visited any gym this month."""
    month = _current_month()
    start = f"{month}-01"
    # End of month: use next month's first day
    year, mon = int(month[:4]), int(month[5:])
    if mon == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{mon + 1:02d}-01"

    res = (
        db.table("gym_visits")
        .select("visited_at")
        .eq("user_id", user_id)
        .gte("visited_at", start)
        .lt("visited_at", end)
        .execute()
    )
    if not res.data:
        return 0
    # Count distinct days
    days = set(row["visited_at"] for row in res.data)
    return len(days)


def _count_user_unique_gyms_month(db, user_id: str) -> int:
    """Count distinct gyms visited this month."""
    month = _current_month()
    start = f"{month}-01"
    year, mon = int(month[:4]), int(month[5:])
    if mon == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{mon + 1:02d}-01"

    res = (
        db.table("gym_visits")
        .select("gym_name")
        .eq("user_id", user_id)
        .gte("visited_at", start)
        .lt("visited_at", end)
        .execute()
    )
    if not res.data:
        return 0
    return len(set(row["gym_name"] for row in res.data))


def _count_user_prs_today(db, user_id: str) -> int:
    """Count PRs registered today."""
    today = date.today().isoformat()
    res = (
        db.table("lifting_prs")
        .select("id")
        .eq("user_id", user_id)
        .eq("pr_date", today)
        .execute()
    )
    return len(res.data) if res.data else 0


def _count_user_prs_month(db, user_id: str) -> int:
    """Count PRs registered this month."""
    month = _current_month()
    start = f"{month}-01"
    year, mon = int(month[:4]), int(month[5:])
    if mon == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{mon + 1:02d}-01"

    res = (
        db.table("lifting_prs")
        .select("id")
        .eq("user_id", user_id)
        .gte("pr_date", start)
        .lt("pr_date", end)
        .execute()
    )
    return len(res.data) if res.data else 0


def _count_user_distinct_pr_exercises_today(db, user_id: str) -> int:
    """Count distinct exercises with PRs today."""
    today = date.today().isoformat()
    res = (
        db.table("lifting_prs")
        .select("exercise_name")
        .eq("user_id", user_id)
        .eq("pr_date", today)
        .execute()
    )
    if not res.data:
        return 0
    return len(set(row["exercise_name"] for row in res.data))


def _count_user_distinct_pr_exercises_month(db, user_id: str) -> int:
    """Count distinct exercises with PRs this month."""
    month = _current_month()
    start = f"{month}-01"
    year, mon = int(month[:4]), int(month[5:])
    if mon == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{mon + 1:02d}-01"

    res = (
        db.table("lifting_prs")
        .select("exercise_name")
        .eq("user_id", user_id)
        .gte("pr_date", start)
        .lt("pr_date", end)
        .execute()
    )
    if not res.data:
        return 0
    return len(set(row["exercise_name"] for row in res.data))


def _compute_auto_progress(db, user_id: str, challenge: dict) -> int:
    """Compute the automatic progress for a challenge based on its category and type."""
    cat = challenge.get("category", "")
    ch_type = challenge.get("type", "daily")
    is_daily = ch_type == "daily"

    if cat == "gym_visits":
        if is_daily:
            return _count_user_gym_visits_today(db, user_id)
        else:
            return _count_user_gym_visits_month(db, user_id)

    elif cat == "prs":
        title_lower = challenge.get("title", "").lower()
        # Check if it's about distinct exercises
        if "ejercicio" in title_lower or "distintos" in title_lower or "diferentes" in title_lower:
            if is_daily:
                return _count_user_distinct_pr_exercises_today(db, user_id)
            else:
                return _count_user_distinct_pr_exercises_month(db, user_id)
        else:
            if is_daily:
                return _count_user_prs_today(db, user_id)
            else:
                return _count_user_prs_month(db, user_id)

    elif cat == "exploration":
        if is_daily:
            # For daily exploration, count unique gyms today
            return _count_user_gym_visits_today(db, user_id)
        else:
            return _count_user_unique_gyms_month(db, user_id)

    elif cat == "consistency":
        # Consistency: combine gym visits days + PR count
        if is_daily:
            return _count_user_gym_visits_today(db, user_id)
        else:
            return _count_user_gym_visits_month(db, user_id)

    return 0


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/challenges/daily")
def get_daily_challenges():
    """Return all daily challenges for today."""
    db = get_supabase_client()
    today = date.today().isoformat()

    res = (
        db.table("challenges")
        .select("*")
        .eq("type", "daily")
        .eq("active_date", today)
        .execute()
    )
    return res.data or []


@router.get("/challenges/monthly")
def get_monthly_challenges():
    """Return all monthly challenges for the current month."""
    db = get_supabase_client()
    month = _current_month()

    res = (
        db.table("challenges")
        .select("*")
        .eq("type", "monthly")
        .eq("month", month)
        .execute()
    )
    return res.data or []


@router.get("/challenges")
def list_challenges():
    """List all available challenges."""
    db = get_supabase_client()
    res = db.table("challenges").select("*").order("created_at", desc=True).execute()
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


@router.get("/users/{user_id}/challenges/active")
def get_active_challenges_with_progress(user_id: str):
    """Return all ACTIVE challenges (daily for today + monthly for current month)
    with the user's progress embedded.
    """
    db = get_supabase_client()
    today = date.today().isoformat()
    month = _current_month()

    # Fetch daily challenges for today
    daily_res = (
        db.table("challenges")
        .select("*")
        .eq("type", "daily")
        .eq("active_date", today)
        .order("difficulty")
        .execute()
    )

    # Fetch monthly challenges for current month
    monthly_res = (
        db.table("challenges")
        .select("*")
        .eq("type", "monthly")
        .eq("month", month)
        .order("difficulty")
        .execute()
    )

    all_challenges = (daily_res.data or []) + (monthly_res.data or [])
    if not all_challenges:
        return []

    # Fetch user progress
    challenge_ids = [ch["id"] for ch in all_challenges]
    uc_res = (
        db.table("user_challenges")
        .select("challenge_id, progress, completed, claimed_at")
        .eq("user_id", user_id)
        .in_("challenge_id", challenge_ids)
        .execute()
    )
    progress_map = {
        row["challenge_id"]: row
        for row in (uc_res.data or [])
    }

    # Difficulty sort order
    diff_order = {"easy": 0, "medium": 1, "hard": 2, "legendary": 3}

    result = []
    for ch in all_challenges:
        user_prog = progress_map.get(ch["id"], {})
        result.append({
            **ch,
            "user_progress": user_prog.get("progress", 0),
            "completed": user_prog.get("completed", False),
            "claimed": user_prog.get("claimed_at") is not None,
            "_diff_order": diff_order.get(ch.get("difficulty", "easy"), 0),
        })

    # Sort: daily first, then by difficulty
    result.sort(key=lambda x: (0 if x["type"] == "daily" else 1, x["_diff_order"]))
    # Remove internal sort key
    for r in result:
        r.pop("_diff_order", None)

    return result


@router.get("/users/{user_id}/challenges/all")
def get_all_challenges_with_progress(user_id: str):
    """Return ALL challenges with the user's progress embedded.
    Challenges the user hasn't started show progress=0, completed=False."""
    db = get_supabase_client()

    # Fetch all challenges
    ch_res = db.table("challenges").select("*").order("created_at").execute()
    all_challenges = ch_res.data or []

    # Fetch user progress for all challenges at once
    uc_res = (
        db.table("user_challenges")
        .select("challenge_id, progress, completed, claimed_at")
        .eq("user_id", user_id)
        .execute()
    )
    # Map: challenge_id → {progress, completed}
    progress_map = {
        row["challenge_id"]: row
        for row in (uc_res.data or [])
    }

    result = []
    for ch in all_challenges:
        user_progress = progress_map.get(ch["id"], {})
        result.append({
            **ch,
            "user_progress": user_progress.get("progress", 0),
            "completed": user_progress.get("completed", False),
            "claimed": user_progress.get("claimed_at") is not None,
        })

    return result


@router.post("/users/{user_id}/challenges/sync")
def sync_challenge_progress(user_id: str):
    """Sync the user's auto-tracked challenge progress.
    Counts gym visits, PRs, etc. and updates user_challenges accordingly.
    Returns the number of challenges updated.
    """
    db = get_supabase_client()
    today = date.today().isoformat()
    month = _current_month()

    # Fetch active auto-tracked challenges
    daily_res = (
        db.table("challenges")
        .select("*")
        .eq("type", "daily")
        .eq("active_date", today)
        .eq("auto_track", True)
        .execute()
    )
    monthly_res = (
        db.table("challenges")
        .select("*")
        .eq("type", "monthly")
        .eq("month", month)
        .eq("auto_track", True)
        .execute()
    )

    challenges = (daily_res.data or []) + (monthly_res.data or [])
    if not challenges:
        return {"synced": 0}

    # Fetch existing user_challenges
    challenge_ids = [ch["id"] for ch in challenges]
    uc_res = (
        db.table("user_challenges")
        .select("*")
        .eq("user_id", user_id)
        .in_("challenge_id", challenge_ids)
        .execute()
    )
    uc_map = {
        row["challenge_id"]: row
        for row in (uc_res.data or [])
    }

    synced = 0
    for ch in challenges:
        progress = _compute_auto_progress(db, user_id, ch)
        progress = min(progress, ch["goal"])  # Cap at goal
        completed = progress >= ch["goal"]

        existing = uc_map.get(ch["id"])
        if existing:
            # Only update if progress changed and not already claimed
            if existing.get("claimed_at") is not None:
                continue  # Already claimed, don't touch
            if existing["progress"] != progress:
                db.table("user_challenges").update({
                    "progress": progress,
                    "completed": completed,
                }).eq("id", existing["id"]).execute()
                synced += 1
        else:
            # Insert new record
            db.table("user_challenges").insert({
                "user_id": user_id,
                "challenge_id": ch["id"],
                "progress": progress,
                "completed": completed,
            }).execute()
            synced += 1

    return {"synced": synced}


@router.post("/users/{user_id}/challenges/{challenge_id}/claim")
def claim_challenge(user_id: str, challenge_id: str):
    """Claim the reward for a completed challenge.
    Awards XP, updates level, marks claimed_at.
    """
    db = get_supabase_client()

    # Get challenge info
    ch_res = db.table("challenges").select("*").eq("id", challenge_id).single().execute()
    if not ch_res.data:
        raise HTTPException(status_code=404, detail="Challenge not found")
    challenge = ch_res.data

    # Get user_challenge record
    uc_res = (
        db.table("user_challenges")
        .select("*")
        .eq("user_id", user_id)
        .eq("challenge_id", challenge_id)
        .single()
        .execute()
    )

    if not uc_res.data:
        raise HTTPException(status_code=400, detail="No progress record found. Sync first.")

    uc = uc_res.data

    # Check already claimed
    if uc.get("claimed_at") is not None:
        raise HTTPException(status_code=400, detail="Reward already claimed")

    # Check if completed
    if not uc.get("completed", False) and uc.get("progress", 0) < challenge["goal"]:
        raise HTTPException(status_code=400, detail="Challenge not completed yet")

    # Mark as claimed
    db.table("user_challenges").update({
        "completed": True,
        "claimed_at": datetime.utcnow().isoformat(),
    }).eq("id", uc["id"]).execute()

    # Award XP
    xp_result = award_xp_and_check_level(user_id, challenge["xp_reward"])

    return {
        "challenge_id": challenge_id,
        "user_id": user_id,
        "xp_awarded": challenge["xp_reward"],
        "total_xp": xp_result.get("total_xp", 0),
        "current_xp": xp_result.get("current_xp", 0),
        "max_xp": xp_result.get("max_xp", 200),
        "xp_percent": xp_result.get("xp_percent", 0),
        "level": xp_result.get("level", 1),
        "title": xp_result.get("title", "Principiante"),
        "leveled_up": xp_result.get("leveled_up", False),
        "previous_level": xp_result.get("previous_level", 1),
    }


@router.post("/users/{user_id}/challenges/{challenge_id}/progress")
def update_challenge_progress(user_id: str, challenge_id: str, body: ChallengeProgressUpdate):
    """Update user's progress on a challenge. Marks as completed if goal reached.
    Note: Does NOT award XP. Use the /claim endpoint to claim rewards."""
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

    if uc_res.data:
        # Don't update if already claimed
        if uc_res.data.get("claimed_at") is not None:
            return {
                "challenge_id": challenge_id,
                "progress": uc_res.data["progress"],
                "goal": challenge["goal"],
                "completed": True,
                "claimed": True,
                "xp_awarded": 0,
            }

        upd = db.table("user_challenges").update({
            "progress": body.progress,
            "completed": completed,
        }).eq("id", uc_res.data["id"]).execute()
        if not upd.data:
            raise HTTPException(status_code=400, detail="Could not update progress")
    else:
        ins = db.table("user_challenges").insert({
            "user_id": user_id,
            "challenge_id": challenge_id,
            "progress": body.progress,
            "completed": completed,
        }).execute()
        if not ins.data:
            raise HTTPException(status_code=400, detail="Could not create progress record")

    return {
        "challenge_id": challenge_id,
        "user_id": user_id,
        "progress": body.progress,
        "goal": challenge["goal"],
        "completed": completed,
        "claimed": False,
        "xp_awarded": 0,
    }
