from fastapi import APIRouter
from database import get_supabase_client
from utils import level_info, get_title, XP_PER_LEVEL

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get("/")
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

    ranking = []
    for i, user in enumerate(users):
        info = level_info(user["total_xp"])
        ranking.append({
            **user,
            "rank": i + 1,
            "level": info["level"],
            "title": info["title"],
        })

    return ranking
