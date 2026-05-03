import asyncio
from database import get_supabase_client

db = get_supabase_client()
res = db.table("lifting_prs").select("*").execute()
print(f"Number of lifting_prs: {len(res.data)}")

res2 = db.table("gym_visits").select("*").execute()
print(f"Number of gym_visits: {len(res2.data)}")

res3 = db.table("users").select("id, username, handle").execute()
print(f"Users in DB:")
for u in res3.data:
    print(f" - {u['username']} ({u['handle']})")
