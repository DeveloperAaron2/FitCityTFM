from fastapi.testclient import TestClient
from main import app
import traceback

client = TestClient(app)
try:
    response = client.get("/ranking/prs")
    print("Status:", response.status_code)
    print("Body length:", len(response.text))
    if response.status_code == 500:
        print("Response:", response.text)
except Exception as e:
    print("Exception during request!")
    traceback.print_exc()
