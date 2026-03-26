import urllib.request
import urllib.parse
import json
import time
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

queries = [
    ("Gimanasio Test Trabajo", "Calle del Poeta Joan Maragall 38, Madrid, Spain"),
    ("Gimnasio Casa Mike", "Calle del Horizon 3,Orcasitas, Madrid, Spain"),
    ("Calle Casa Dani", "Avenida de Barranquilla 5, Madrid, Spain"),
    ("Calle Casa Aaron", "Calle Ana Frank 3, Valdemoro, Spain")
]

new_nodes = []
base_id: int = 9000000000

for name, q in queries:
    url = "https://nominatim.openstreetmap.org/search?q=" + urllib.parse.quote(q) + "&format=json&limit=1"
    req = urllib.request.Request(url, headers={'User-Agent': 'FitCityTfm/1.0 (miguelcalzada)'})
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            res = json.loads(response.read().decode())
            if res:
                lat = float(res[0]["lat"])
                lon = float(res[0]["lon"])
                print(f"Found {name}: {lat}, {lon}")
                node = {
                    "type": "node",
                    "id": base_id,
                    "lat": lat,
                    "lon": lon,
                    "tags": {
                        "name": name,
                        "amenity": "gym"
                    }
                }
                new_nodes.append(node)
                base_id += 1  # type: ignore
            else:
                print(f"Not found: {q}")
    except Exception as e:
        print(f"Error {name}: {e}")
    time.sleep(1)

if new_nodes:
    try:
        with open("backend/madrid_gyms.json", "r") as f:
            data = json.load(f)
        
        data.setdefault("elements", []).extend(new_nodes)
        
        with open("backend/madrid_gyms.json", "w") as f:
            json.dump(data, f, indent=2)
        print(f"Added {len(new_nodes)} gyms to madrid_gyms.json successfully.")
    except Exception as e:
        print(f"Failed to append to JSON: {e}")
