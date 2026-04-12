"""
utils.py — Lógica compartida de niveles y títulos.
Importar desde cualquier router para evitar duplicación.

PROGRESSIVE XP CURVE:
  Level 1 → 2:    200 XP
  Level 2 → 3:    400 XP
  Level 3 → 4:    700 XP
  Level 4 → 5:  1,100 XP
  Level 5 → 6:  1,600 XP
  Level 6 → 7:  2,200 XP
  Level 7 → 8:  3,000 XP
  Level 8 → 9:  4,000 XP
  Level 9 → 10: 5,200 XP
  Level 10+:    +1,500 per additional level
"""

from typing import Optional


def _xp_for_level(level: int) -> int:
    """Return the XP required to go FROM `level` to `level + 1`.

    Uses a progressive curve so early levels are easy and later levels are hard.
    """
    # Base table for levels 1–10
    _TABLE = {
        1: 200,
        2: 400,
        3: 700,
        4: 1100,
        5: 1600,
        6: 2200,
        7: 3000,
        8: 4000,
        9: 5200,
    }
    if level < 1:
        return 200
    if level <= 9:
        return _TABLE[level]
    # Level 10+: 5200 + 1500 for each level beyond 9
    return 5200 + (level - 9) * 1500


def _cumulative_xp_for_level(level: int) -> int:
    """Return the TOTAL XP needed to reach `level` (i.e. the sum of all previous levels)."""
    total = 0
    for lv in range(1, level):
        total += _xp_for_level(lv)
    return total


def compute_level(total_xp: int) -> int:
    """Return the user's level given their total accumulated XP."""
    level = 1
    remaining = total_xp
    while True:
        required = _xp_for_level(level)
        if remaining < required:
            break
        remaining -= required
        level += 1
    return level


# Mapa nivel → título
_TITLES = {
    1: "Principiante", 2: "Aprendiz",  3: "Atleta",
    4: "Guerrero",     5: "Campeón",   6: "Élite",
    7: "Maestro",      8: "Gran Maestro", 9: "Leyenda", 10: "FitGod",
}


def get_title(level: int) -> str:
    if level <= 10:
        return _TITLES.get(level, "FitGod")
    return "FitGod"


def level_info(total_xp: int) -> dict:
    """Return full level/XP breakdown for the frontend.

    Returns:
        level:      current level number
        title:      level title string
        total_xp:   raw total XP (passed through)
        current_xp: XP progress within the current level
        max_xp:     XP required to complete the current level
        xp_percent: percentage progress within the current level (0–100)
    """
    lv = compute_level(total_xp)
    xp_at_level_start = _cumulative_xp_for_level(lv)
    xp_for_next = _xp_for_level(lv)
    current_xp = total_xp - xp_at_level_start
    pct = round((current_xp / xp_for_next) * 100, 1) if xp_for_next > 0 else 100

    return {
        "level": lv,
        "title": get_title(lv),
        "total_xp": total_xp,
        "current_xp": current_xp,
        "max_xp": xp_for_next,
        "xp_percent": min(pct, 100),
    }


def award_xp_and_check_level(user_id: str, xp_amount: int) -> dict:
    """Award XP to a user, update user_levels, and return level-up info.

    Returns:
        {
            "total_xp": int,
            "xp_awarded": int,
            "level": int,
            "current_xp": int,
            "max_xp": int,
            "xp_percent": float,
            "title": str,
            "leveled_up": bool,
            "previous_level": int,
        }
    """
    # Import here to avoid circular imports
    from database import get_supabase_client

    db = get_supabase_client()

    # Fetch current XP
    res = db.table("users").select("total_xp").eq("id", user_id).single().execute()
    if not res.data:
        return {"xp_awarded": 0, "leveled_up": False}

    old_xp = res.data["total_xp"]
    new_xp = old_xp + xp_amount

    prev_level = compute_level(old_xp)
    info = level_info(new_xp)

    # Update total_xp
    db.table("users").update({"total_xp": new_xp}).eq("id", user_id).execute()

    # Upsert user_levels
    db.table("user_levels").upsert(
        {"user_id": user_id, "level": info["level"], "max_xp": info["max_xp"]},
        on_conflict="user_id",
    ).execute()

    return {
        **info,
        "xp_awarded": xp_amount,
        "leveled_up": info["level"] > prev_level,
        "previous_level": prev_level,
    }


# Keep backward-compatible constant (used by auth.py for initial level row)
XP_PER_LEVEL = _xp_for_level(1)  # 200 for level 1→2
