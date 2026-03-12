from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import traceback
from utils import level_info, XP_PER_LEVEL

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: str
    handle: str          # e.g. aaron_fit (without the @)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_db():
    """Import here to get a clear error if the key is wrong."""
    from database import get_supabase_client
    try:
        return get_supabase_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/register")
def register(body: RegisterRequest):
    """Create a Supabase Auth account and a matching row in the users table."""
    db = _get_db()

    # 1. Create auth user in Supabase Auth
    try:
        auth_res = db.auth.sign_up({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error en Supabase Auth: {str(e)}")

    if not auth_res.user:
        raise HTTPException(status_code=400, detail="No se pudo crear el usuario de autenticación")

    user_id = auth_res.user.id

    # 2. Insert profile row in public.users table
    handle = body.handle.lstrip("@")
    try:
        profile_res = db.table("users").insert({
            "id": user_id,
            "username": body.username,
            "handle": f"@{handle}",
            "total_xp": 0,
        }).execute()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Usuario auth creado pero error al insertar perfil: {str(e)}. "
                   "Comprueba que has ejecutado el schema SQL y que las RLS policies están configuradas."
        )

    if not profile_res.data:
        raise HTTPException(
            status_code=500,
            detail="Usuario auth creado pero el insert del perfil no devolvió datos. "
                   "Comprueba las RLS policies en Supabase."
        )

    # Insert initial row in user_levels (level 1, max_xp = XP_PER_LEVEL)
    try:
        db.table("user_levels").insert({
            "user_id": user_id,
            "level": 1,
            "max_xp": XP_PER_LEVEL,   # umbral para subir a nivel 2
        }).execute()
    except Exception:
        pass  # Non-fatal: level row will be created on first XP update

    return {
        "user_id": user_id,
        "email": body.email,
        "username": body.username,
        "handle": f"@{handle}",
        "access_token": auth_res.session.access_token if auth_res.session else None,
        "refresh_token": auth_res.session.refresh_token if auth_res.session else None,
    }


@router.post("/login")
def login(body: LoginRequest):
    """Sign in with email + password. Returns JWT access_token."""
    db = _get_db()

    try:
        auth_res = db.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        traceback.print_exc()
        error_msg = str(e)
        if "Email not confirmed" in error_msg:
            raise HTTPException(
                status_code=401,
                detail="Email no confirmado. Revisa tu bandeja de entrada o desactiva la confirmación de email en Supabase (Authentication → Settings → Email → desmarca 'Confirm email')."
            )
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    if not auth_res.user or not auth_res.session:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    user_id = auth_res.user.id

    # Fetch profile from our users table
    try:
        profile_res = db.table("users").select("*").eq("id", user_id).single().execute()
        profile = profile_res.data or {}
    except Exception:
        profile = {}

    total_xp = profile.get("total_xp", 0)
    lv_info = level_info(total_xp)

    return {
        "access_token": auth_res.session.access_token,
        "refresh_token": auth_res.session.refresh_token,
        "user": {
            "id": user_id,
            "email": auth_res.user.email,
            "username": profile.get("username", ""),
            "handle": profile.get("handle", ""),
            "total_xp": total_xp,
            **lv_info,
        }
    }


@router.post("/logout")
def logout():
    """Sign out the current user."""
    db = _get_db()
    try:
        db.auth.sign_out()
    except Exception:
        pass
    return {"message": "Sesión cerrada correctamente"}
