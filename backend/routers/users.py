from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from database import get_supabase_client
from utils import compute_level, get_title, level_info, award_xp_and_check_level, _xp_for_level
from config import get_settings


router = APIRouter(prefix="/users", tags=["users"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    handle: str
    avatar_url: Optional[str] = None


class UserXPUpdate(BaseModel):
    xp_to_add: int


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/{user_id}")
def get_user(user_id: str):
    """Get full user profile including computed level, XP and title."""
    db = get_supabase_client()
    res = db.table("users").select("*").eq("id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")

    user = res.data
    info = level_info(user["total_xp"])
    return {**user, **info}


@router.get("/{user_id}/level")
def get_user_level(user_id: str):
    """Get the computed level info for a user."""
    db = get_supabase_client()
    res = db.table("users").select("total_xp").eq("id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")
    return level_info(res.data["total_xp"])


@router.post("")
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
    """Add XP to a user. Uses centralized XP+level logic."""
    result = award_xp_and_check_level(user_id, body.xp_to_add)
    if result.get("xp_awarded", 0) == 0 and not result.get("total_xp"):
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user_id, **result}


@router.put("/{user_id}/avatar")
async def upload_avatar(user_id: str, file: UploadFile = File(...)):
    """Upload or replace a user's profile avatar.
    Stores the image in the Supabase 'avatars' bucket and updates users.avatar_url.
    """
    import os

    # Validate MIME type
    content_type = file.content_type or ""
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: '{content_type}'. Se esperan: {', '.join(allowed_types)}"
        )

    # Read file bytes (max 5 MB)
    MAX_BYTES = 5 * 1024 * 1024
    image_bytes = await file.read()
    if len(image_bytes) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="La imagen supera el límite de 5 MB.")

    # Determine extension
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
    ext = ext_map.get(content_type, "jpg")
    storage_path = f"{user_id}.{ext}"

    db = get_supabase_client()

    # Upload to Supabase Storage (upsert = overwrite if exists)
    try:
        db.storage.from_("avatars").upload(
            path=storage_path,
            file=image_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error subiendo imagen: {str(e)}")

    # Build public URL
    settings = get_settings()
    public_url = f"{settings.supabase_url}/storage/v1/object/public/avatars/{storage_path}"

    # Update users.avatar_url
    upd = db.table("users").update({"avatar_url": public_url}).eq("id", user_id).execute()
    if not upd.data:
        raise HTTPException(status_code=400, detail="No se pudo actualizar la URL del avatar.")

    return {"avatar_url": public_url}
