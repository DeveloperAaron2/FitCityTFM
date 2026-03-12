from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from datetime import date
from database import get_supabase_client

router = APIRouter(prefix="/users/{user_id}/lifting-prs", tags=["lifting_prs"])

# ── Constantes de validación de vídeo ─────────────────────────────────────────
_MAX_VIDEO_SIZE_MB = 200
_MAX_VIDEO_BYTES = _MAX_VIDEO_SIZE_MB * 1024 * 1024
_ALLOWED_MIME_PREFIXES = ("video/",)
_ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


# ── Schemas ────────────────────────────────────────────────────────────────────

class LiftingPRCreate(BaseModel):
    gym_name: str               # Gym where the PR was achieved
    exercise_name: str          # e.g. "Press de banca"
    exercise_emoji: str         # e.g. "🏋️"
    weight_kg: float
    reps: Optional[int] = 1    # Default 1 rep max
    pr_date: Optional[date] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/validate-video")
async def validate_pr_video(user_id: str, video: UploadFile = File(...)):
    """
    Validates that the uploaded file is a proper video before allowing a PR submission.
    The video is read and validated but NEVER stored in the database.

    Checks:
    - MIME type starts with 'video/'
    - File extension is in the allowed set
    - File size does not exceed the limit
    """
    import os

    # 1. Validate MIME type
    content_type = video.content_type or ""
    if not any(content_type.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: '{content_type}'. Se esperaba un vídeo.",
        )

    # 2. Validate file extension
    ext = os.path.splitext(video.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Extensión no permitida: '{ext}'. Permitidas: {', '.join(_ALLOWED_EXTENSIONS)}",
        )

    # 3. Read and validate file size (stream in chunks to avoid loading all into memory)
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1 MB chunks
    while True:
        chunk = await video.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > _MAX_VIDEO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"El vídeo supera el tamaño máximo permitido de {_MAX_VIDEO_SIZE_MB} MB.",
            )

    await video.close()

    size_mb = round(total_bytes / (1024 * 1024), 2)
    return {
        "valid": True,
        "filename": video.filename,
        "content_type": content_type,
        "size_mb": size_mb,
        "message": f"Vídeo validado correctamente ({size_mb} MB). Puedes registrar tu PR.",
    }

@router.get("/")
def get_lifting_prs(
    user_id: str,
    gym_name: Optional[str] = Query(default=None, description="Filter PRs by gym name"),
):
    """Return personal records for a user. Optionally filter by gym."""
    db = get_supabase_client()
    query = (
        db.table("lifting_prs")
        .select("*")
        .eq("user_id", user_id)
        .order("pr_date", desc=True)
    )
    if gym_name:
        query = query.eq("gym_name", gym_name)

    res = query.execute()
    return res.data or []


@router.get("/by-gym")
def get_prs_by_gym(user_id: str):
    """Return all PRs grouped by gym."""
    db = get_supabase_client()
    res = (
        db.table("lifting_prs")
        .select("*")
        .eq("user_id", user_id)
        .order("gym_name")
        .order("exercise_name")
        .execute()
    )
    records = res.data or []

    # Group by gym_name
    grouped: dict[str, list] = {}
    for pr in records:
        gym = pr.get("gym_name") or "Sin gimnasio"
        grouped.setdefault(gym, []).append(pr)

    return [{"gym_name": gym, "prs": prs} for gym, prs in grouped.items()]


@router.post("/")
def upsert_lifting_pr(user_id: str, body: LiftingPRCreate):
    """Create or update a PR for a specific gym+exercise combo.
    Updates only if the new weight is heavier than the existing PR at that gym.
    """
    db = get_supabase_client()

    # Check if a PR exists for this user + gym + exercise
    existing = (
        db.table("lifting_prs")
        .select("id, weight_kg")
        .eq("user_id", user_id)
        .eq("gym_name", body.gym_name)
        .eq("exercise_name", body.exercise_name)
        .single()
        .execute()
    )

    payload = {
        "user_id": user_id,
        "gym_name": body.gym_name,
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
                detail=(
                    f"El nuevo peso ({body.weight_kg} kg) no supera el PR actual "
                    f"en {body.gym_name} ({existing.data['weight_kg']} kg)"
                ),
            )
        res = db.table("lifting_prs").update(payload).eq("id", existing.data["id"]).execute()
        is_new = False
    else:
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
