from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from database import get_supabase_client
from utils import compute_level, get_title, level_info, XP_PER_LEVEL
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
    """Get the stored level info for a user from the user_levels table."""
    db = get_supabase_client()

    # Try user_levels first (source of truth after any XP update)
    ul = (
        db.table("user_levels")
        .select("level, max_xp")
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if ul.data:
        return ul.data

    # Fallback: compute from total_xp if user_levels row doesn't exist yet
    res = db.table("users").select("total_xp").eq("id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")
    lv = compute_level(res.data["total_xp"])
    return {"level": lv, "max_xp": XP_PER_LEVEL * lv}


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
    """Add XP to a user. Updates user_levels table and returns new level info."""
    db = get_supabase_client()

    # Fetch current XP
    res = db.table("users").select("total_xp").eq("id", user_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User not found")

    new_total_xp = res.data["total_xp"] + body.xp_to_add

    # Update total_xp in users table
    upd = db.table("users").update({"total_xp": new_total_xp}).eq("id", user_id).execute()
    if not upd.data:
        raise HTTPException(status_code=400, detail="Could not update XP")

    # Compute level and upsert into user_levels table
    lv = compute_level(new_total_xp)
    max_xp = XP_PER_LEVEL * lv
    db.table("user_levels").upsert(
        {"user_id": user_id, "level": lv, "max_xp": max_xp},
        on_conflict="user_id",
    ).execute()

    return {
        "user_id": user_id,
        "total_xp": new_total_xp,
        "level": lv,
        "max_xp": max_xp,
        "title": get_title(lv),
    }


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
