from fastapi import APIRouter, Query
from database import get_supabase_client
from utils import level_info, get_title, XP_PER_LEVEL

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get("/prs")
def get_global_prs(limit: int = 50):
    """Return top PRs globally sorted by weight."""
    db = get_supabase_client()
    res = (
        db.table("lifting_prs")
        .select("*, users!inner(username, handle, avatar_url)")
        .order("weight_kg", desc=True)
        .limit(limit)
        .execute()
    )
    records = res.data or []

    # Fetch gym_best_lifts to map video URLs for the Global PRs
    bl_res = db.table("gym_best_lifts").select("gym_name, exercise_name, user_id, video_url").execute()
    bl_data = bl_res.data or []
    
    bl_map = {(r["gym_name"], r["exercise_name"], r["user_id"]): r["video_url"] for r in bl_data}
    
    for r in records:
        key = (r.get("gym_name"), r.get("exercise_name"), r.get("user_id"))
        if key in bl_map:
            r["video_url"] = bl_map[key]

    return records


@router.get("/prs/by-gym")
def get_prs_by_gym(top_per_gym: int = 5):
    """Return top PRs grouped by gym, sorted by weight descending within each gym.
    Also includes gym best lift video info for each gym.
    """
    db = get_supabase_client()
    res = (
        db.table("lifting_prs")
        .select("*, users!inner(username, handle, avatar_url)")
        .order("weight_kg", desc=True)
        .execute()
    )
    records = res.data or []

    # Fetch all gym best lifts (with user info for display)
    best_lifts_res = (
        db.table("gym_best_lifts")
        .select("*, users!inner(username, handle, avatar_url)")
        .execute()
    )
    best_lifts = best_lifts_res.data or []

    # Index best lifts by gym_name
    best_lifts_by_gym: dict[str, list] = {}
    for bl in best_lifts:
        gym = bl.get("gym_name") or "Sin gimnasio"
        best_lifts_by_gym.setdefault(gym, []).append(bl)

    # Group PRs by gym_name
    grouped: dict[str, list] = {}
    for pr in records:
        gym = pr.get("gym_name") or "Sin gimnasio"
        grouped.setdefault(gym, []).append(pr)

    # Build response: sorted alphabetically by gym name, top N PRs each
    result = []
    for gym_name in sorted(grouped.keys()):
        prs = grouped[gym_name]  # already sorted by weight_kg desc from the query
        gym_best = best_lifts_by_gym.get(gym_name, [])
        result.append({
            "gym_name": gym_name,
            "total_prs": len(prs),
            "top_prs": prs[:top_per_gym],
            "has_videos": len(gym_best) > 0,
            "best_lifts": gym_best,
        })

    return result


@router.get("/prs/by-gym/{gym_name}/best-lifts")
def get_gym_best_lifts(gym_name: str):
    """Return the best validated lift videos for a specific gym."""
    db = get_supabase_client()
    res = (
        db.table("gym_best_lifts")
        .select("*, users!inner(username, handle, avatar_url)")
        .eq("gym_name", gym_name)
        .order("weight_kg", desc=True)
        .execute()
    )
    return res.data or []


@router.get("")
def get_ranking(limit: int = 20):
    """Return top users sorted by total XP descending."""
    db = get_supabase_client()
    res = (
        db.table("users")
        .select("id, username, handle, avatar_url, total_xp")
        .order("total_xp", desc=True)
        .limit(limit)
        .execute()
    )
    users = res.data or []

    # Add rank, level and title to each user
    XP_PER_LEVEL = 5000
    TITLES = {
        1: "Principiante", 2: "Aprendiz", 3: "Atleta",
        4: "Guerrero", 5: "Campeón", 6: "Élite",
        7: "Maestro", 8: "Gran Maestro", 9: "Leyenda", 10: "FitGod",
    }

    ranking = []
    for i, user in enumerate(users):
        total_xp = user["total_xp"]
        level = (total_xp // XP_PER_LEVEL) + 1
        bucket = min((level - 1) // 3 + 1, 10)
        ranking.append({
            **user,
            "rank": i + 1,
            "level": level,
            "title": TITLES.get(bucket, "FitMaster"),
        })

    return ranking
