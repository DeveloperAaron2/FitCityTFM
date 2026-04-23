from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import traceback
from utils import level_info, _xp_for_level

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
            "max_xp": _xp_for_level(1),   # umbral para subir a nivel 2
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
            "avatar_url": profile.get("avatar_url", None),
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


# ── Google OAuth Callback ──────────────────────────────────────────────────────

class GoogleCallbackRequest(BaseModel):
    access_token: str
    refresh_token: str


@router.post("/google/callback")
def google_callback(body: GoogleCallbackRequest):
    """
    Called by the frontend after Supabase OAuth redirect.
    Verifies the token, creates a profile row in public.users if it's a new user,
    and returns the same session format as /auth/login.
    """
    db = _get_db()

    # 1. Restore the session from the tokens provided by the frontend
    try:
        session_res = db.auth.set_session(body.access_token, body.refresh_token)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=401, detail=f"Token de Google inválido: {str(e)}")

    if not session_res.user or not session_res.session:
        raise HTTPException(status_code=401, detail="No se pudo verificar el token de Google")

    user = session_res.user
    user_id = user.id
    email = user.email or ""

    # 2. Try to fetch existing profile
    try:
        profile_res = db.table("users").select("*").eq("id", user_id).maybe_single().execute()
        profile = profile_res.data
    except Exception:
        profile = None

    # 3. First time with Google — auto-create the profile
    if not profile:
        # Derive a username from the Google display name or email
        raw_name = (user.user_metadata or {}).get("full_name") or email.split("@")[0]
        base_handle = raw_name.lower().replace(" ", "_")[:20]

        try:
            insert_res = db.table("users").insert({
                "id": user_id,
                "username": raw_name,
                "handle": f"@{base_handle}",
                "total_xp": 0,
            }).execute()
            profile = insert_res.data[0] if insert_res.data else {}
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Error al crear perfil de usuario Google: {str(e)}"
            )

        # Insert initial level row (non-fatal)
        try:
            db.table("user_levels").insert({
                "user_id": user_id,
                "level": 1,
                "max_xp": _xp_for_level(1),
            }).execute()
        except Exception:
            pass

    total_xp = profile.get("total_xp", 0)
    lv_info = level_info(total_xp)

    return {
        "access_token": session_res.session.access_token,
        "refresh_token": session_res.session.refresh_token,
        "user": {
            "id": user_id,
            "email": email,
            "username": profile.get("username", ""),
            "handle": profile.get("handle", ""),
            "avatar_url": profile.get("avatar_url", None),
            "total_xp": total_xp,
            **lv_info,
        }
    }
