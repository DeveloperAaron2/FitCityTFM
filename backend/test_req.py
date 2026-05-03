import urllib.request
try:
    with urllib.request.urlopen("http://localhost:8000/ranking/prs") as res:
        print(res.read().decode())
except Exception as e:
    print(f"Error ({e.code}):", e.read().decode())
