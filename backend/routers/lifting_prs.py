from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Form
from pydantic import BaseModel
from typing import Optional
from datetime import date
from database import get_supabase_client
from Services.AIService import ai_service
from config import get_settings
import re

router = APIRouter(prefix="/users/{user_id}/lifting-prs", tags=["lifting_prs"])

# ── Standalone router for video-only validation (no user/gym association) ───────
validate_router = APIRouter(prefix="/validate-video", tags=["video_validation"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class LiftingPRCreate(BaseModel):
    gym_name: str
    exercise_name: str          # e.g. "Press de banca"
    exercise_emoji: str         # e.g. "🏋️"
    weight_kg: float
    reps: Optional[int] = 1    # Default 1 rep max
    pr_date: Optional[date] = None

# ── Constants ──────────────────────────────────────────────────────────────────
_ALLOWED_MIME_PREFIXES = ["video/"]
_ALLOWED_EXTENSIONS = [".mp4", ".mov", ".avi", ".webm", ".mkv"]
_MAX_VIDEO_SIZE_MB = 100
_MAX_VIDEO_BYTES = _MAX_VIDEO_SIZE_MB * 1024 * 1024
_BEST_LIFT_XP = 500  # XP awarded for uploading the best lift video at a gym
_GYM_VIDEOS_BUCKET = "gym-videos"

# Exercises allowed for gym best lifts
_ALLOWED_EXERCISES = {"Press de banca", "Sentadilla", "Peso muerto"}


def _sanitize_path(name: str) -> str:
    """Sanitise a name for use as a storage path segment."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip().lower())


def _is_better_lift(new_weight: float, new_reps: int, old_weight: float, old_reps: int) -> bool:
    """Return True if the new lift is strictly better than the old one.
    Priority: higher weight first; if equal, more reps wins.
    """
    if new_weight > old_weight:
        return True
    if new_weight == old_weight and new_reps > old_reps:
        return True
    return False


_PLAUSIBILITY_THRESHOLD = 0.20  # Max 20% increase over previous PR


def _check_weight_plausibility(user_id: str, exercise_name: str, new_weight: float) -> dict | None:
    """Check if the declared weight is plausible based on the user's history.
    Returns a warning dict if the jump is suspicious, or None if OK.
    """
    if new_weight <= 0:
        return None

    db = get_supabase_client()
    existing = (
        db.table("lifting_prs")
        .select("weight_kg")
        .eq("user_id", user_id)
        .eq("exercise_name", exercise_name)
        .order("weight_kg", desc=True)
        .limit(1)
        .execute()
    )

    if not existing.data:
        return None  # First PR for this exercise — no reference

    prev_weight = float(existing.data[0]["weight_kg"])
    if prev_weight <= 0:
        return None

    increase_pct = (new_weight - prev_weight) / prev_weight

    if increase_pct > _PLAUSIBILITY_THRESHOLD:
        return {
            "previous_weight": prev_weight,
            "new_weight": new_weight,
            "increase_percent": round(increase_pct * 100, 1),
            "threshold_percent": round(_PLAUSIBILITY_THRESHOLD * 100, 1),
            "message": (
                f"⚠️ Salto de peso sospechoso: {prev_weight} kg → {new_weight} kg "
                f"(+{round(increase_pct * 100, 1)}%). El máximo habitual es +{round(_PLAUSIBILITY_THRESHOLD * 100)}%."
            ),
        }

    return None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/validate-video")
async def validate_pr_video(
    user_id: str, 
    video: UploadFile = File(...),
    exercise_name: str = Form(...),
    gym_name: str = Form(""),
    weight_kg: float = Form(0),
    reps: int = Form(1),
):
    """
    Validates that the uploaded file is a proper video before allowing a PR submission.
    The video is passed to the AI Service for validation according to powerlifting rules.
    
    If the video is valid AND the lift is the best for that gym+exercise,
    the video is uploaded to Supabase Storage and the gym_best_lifts table is updated.
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

    # 3. Read and validate file size (stream in chunks to avoid loading all into memory at once, accumulate bytes for AI)
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1 MB chunks
    video_bytes = bytearray()
    
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
        video_bytes.extend(chunk)

    await video.close()
    
    # 4. Analyze video via AI Service (movement validation)
    video_data = bytes(video_bytes)
    analysis = await ai_service.analyze_lifting_video(video_data, exercise_name)
    
    if not analysis.get("is_valid", False):
        raise HTTPException(
            status_code=400,
            detail=f"Levantamiento nulo ({analysis.get('confidence', 'low')}): {analysis.get('reason', 'Análisis fallido')}"
        )

    size_mb = round(total_bytes / (1024 * 1024), 2)

    # 5. LAYER 1 — Weight plausibility check
    weight_plausibility_warning = None
    if weight_kg > 0:
        weight_plausibility_warning = _check_weight_plausibility(
            user_id, exercise_name, weight_kg
        )

    # 6. LAYER 2 — AI weight estimation
    weight_ai_check = None
    if weight_kg > 0:
        weight_ai_check = await ai_service.estimate_weight_from_video(
            video_data, exercise_name, weight_kg
        )

    # 7. Check if this is the best lift for this gym+exercise and upload to Storage
    is_gym_best = False
    best_lift_xp_awarded = 0
    video_url = None

    if (
        gym_name.strip()
        and exercise_name.strip() in _ALLOWED_EXERCISES
        and weight_kg > 0
    ):
        is_gym_best, video_url, best_lift_xp_awarded = await _process_gym_best_lift(
            user_id=user_id,
            gym_name=gym_name.strip(),
            exercise_name=exercise_name.strip(),
            weight_kg=weight_kg,
            reps=reps,
            video_bytes=video_data,
            content_type=content_type,
        )

    return {
        "valid": True,
        "filename": video.filename,
        "content_type": content_type,
        "size_mb": size_mb,
        "ai_reason": analysis.get("reason"),
        "ai_confidence": analysis.get("confidence"),
        "is_gym_best": is_gym_best,
        "best_lift_xp_awarded": best_lift_xp_awarded,
        "weight_plausibility_warning": weight_plausibility_warning,
        "weight_ai_check": weight_ai_check,
        "message": f"Vídeo validado correctamente por la IA ({size_mb} MB). Puedes registrar tu PR.",
    }


async def _process_gym_best_lift(
    user_id: str,
    gym_name: str,
    exercise_name: str,
    weight_kg: float,
    reps: int,
    video_bytes: bytes,
    content_type: str,
) -> tuple[bool, str | None, int]:
    """Check if this lift beats the current gym best. If so, upload video and update DB.
    Returns (is_best, video_url, xp_awarded).
    """
    db = get_supabase_client()
    settings = get_settings()

    # Query current best for this gym + exercise
    existing = (
        db.table("gym_best_lifts")
        .select("id, weight_kg, reps, video_url")
        .eq("gym_name", gym_name)
        .eq("exercise_name", exercise_name)
        .limit(1)
        .execute()
    )

    current = existing.data[0] if existing.data else None

    # If there's an existing record, check if the new lift is better
    if current:
        old_weight = float(current["weight_kg"])
        old_reps = int(current["reps"])
        if not _is_better_lift(weight_kg, reps, old_weight, old_reps):
            return (False, None, 0)

    # This IS the best lift — upload the video
    gym_slug = _sanitize_path(gym_name)
    exercise_slug = _sanitize_path(exercise_name)
    storage_path = f"{gym_slug}/{exercise_slug}.mp4"

    try:
        # Delete old video if it exists (upsert handles the file replacement)
        db.storage.from_(_GYM_VIDEOS_BUCKET).upload(
            path=storage_path,
            file=video_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as e:
        # Log but don't fail the validation — the PR can still be saved
        print(f"⚠️ Error uploading gym best lift video: {e}")
        return (False, None, 0)

    # Build public URL
    video_url = f"{settings.supabase_url}/storage/v1/object/public/{_GYM_VIDEOS_BUCKET}/{storage_path}"

    # Upsert gym_best_lifts record
    payload = {
        "gym_name": gym_name,
        "exercise_name": exercise_name,
        "user_id": user_id,
        "weight_kg": weight_kg,
        "reps": reps,
        "video_url": video_url,
    }

    if current:
        db.table("gym_best_lifts").update(payload).eq("id", current["id"]).execute()
    else:
        db.table("gym_best_lifts").insert(payload).execute()

    # Award bonus XP
    xp_res = db.table("users").select("total_xp").eq("id", user_id).limit(1).execute()
    if xp_res.data:
        new_xp = xp_res.data[0]["total_xp"] + _BEST_LIFT_XP
        db.table("users").update({"total_xp": new_xp}).eq("id", user_id).execute()

    return (True, video_url, _BEST_LIFT_XP)


@router.get("")
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


@router.post("")
def upsert_lifting_pr(user_id: str, body: LiftingPRCreate):
    """Create or update a PR for a specific gym+exercise combo.
    Updates only if the new weight is heavier than the existing PR at that gym.
    """
    db = get_supabase_client()

    # Check if a PR exists for this user + gym + exercise
    existing_res = (
        db.table("lifting_prs")
        .select("id, weight_kg")
        .eq("user_id", user_id)
        .eq("gym_name", body.gym_name)
        .eq("exercise_name", body.exercise_name)
        .limit(1)
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

    if existing_res.data and len(existing_res.data) > 0:
        existing = existing_res.data[0]
        if body.weight_kg <= existing["weight_kg"]:
            raise HTTPException(
                status_code=409,
                detail=f"New weight ({body.weight_kg} kg) is not heavier than current PR ({existing['weight_kg']} kg)"
            )
        # Update existing PR
        res = db.table("lifting_prs").update(payload).eq("id", existing["id"]).execute()
        is_new = False
    else:
        # Insert new PR
        res = db.table("lifting_prs").insert(payload).execute()
        is_new = True

    if not res.data:
        raise HTTPException(status_code=400, detail="Could not save PR")

    # Award XP for new PR (+100 XP)
    xp_awarded = 100
    xp_res = db.table("users").select("total_xp").eq("id", user_id).limit(1).execute()
    if xp_res.data and len(xp_res.data) > 0:
        new_xp = xp_res.data[0]["total_xp"] + xp_awarded
        db.table("users").update({"total_xp": new_xp}).eq("id", user_id).execute()

    return {"pr": res.data[0], "is_new_record": is_new, "xp_awarded": xp_awarded}


# ── Standalone video-only validation (no user, no gym, no storage) ─────────────

@validate_router.post("")
async def validate_video_only(
    video: UploadFile = File(...),
    exercise_name: str = Form(...)
):
    """
    Validates a video using the AI service WITHOUT associating it to any user,
    gym, or storing anything in the database. Purely for validation feedback.
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

    # 3. Read and validate file size
    total_bytes = 0
    chunk_size = 1024 * 1024
    video_bytes = bytearray()

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
        video_bytes.extend(chunk)

    await video.close()

    # 4. Analyze video via AI Service
    analysis = await ai_service.analyze_lifting_video(bytes(video_bytes), exercise_name)

    size_mb = round(total_bytes / (1024 * 1024), 2)

    return {
        "is_valid": analysis.get("is_valid", False),
        "reason": analysis.get("reason", "Sin información"),
        "confidence": analysis.get("confidence", "low"),
        "size_mb": size_mb,
        "message": "Levantamiento válido ✅" if analysis.get("is_valid") else "Levantamiento nulo ❌",
    }
