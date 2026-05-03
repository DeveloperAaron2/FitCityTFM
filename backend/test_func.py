from routers.ranking import get_global_prs

try:
    print(get_global_prs())
except Exception as e:
    import traceback
    traceback.print_exc()
