import sys
from supabase import create_client, Client
from functools import lru_cache
from config import get_settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Returns a cached Supabase client singleton.
    Validates that the key looks like a JWT (starts with 'eyJ') before connecting.
    """
    settings = get_settings()

    # ── Validate key format ────────────────────────────────────────────────
    key = settings.supabase_key.strip()
    if not key.startswith("eyJ"):
        print("=" * 60, file=sys.stderr)
        print("❌  ERROR: SUPABASE_KEY inválida en .env", file=sys.stderr)
        print("   La clave que has puesto empieza por:", key[:30], file=sys.stderr)
        print("   Supabase necesita la 'anon key' JWT que empieza por 'eyJ...'", file=sys.stderr)
        print("   Ve a: Supabase Dashboard → Settings → API → anon/public", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        raise RuntimeError(
            "SUPABASE_KEY inválida. Necesitas la 'anon key' (empieza por 'eyJ...'). "
            "Encuéntrala en: Supabase Dashboard → Settings → API → anon/public"
        )

    return create_client(settings.supabase_url, key)
