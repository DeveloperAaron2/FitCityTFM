import asyncio
from database import get_supabase_client

db = get_supabase_client()
res = (
    db.table("lifting_prs")
    .select("*, users!inner(username, avatar_url, handle)")
    .order("weight_kg", desc=True)
    .limit(5)
    .execute()
)
print(res.data)
