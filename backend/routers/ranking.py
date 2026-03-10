from fastapi import APIRouter
from database import get_supabase_client

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
