from database import get_supabase_client
db = get_supabase_client()
try:
    db.table("gym_best_lifts").select("*").execute()
    print("gym_best_lifts works!")
except Exception as e:
    print(f"Error: {e}")
