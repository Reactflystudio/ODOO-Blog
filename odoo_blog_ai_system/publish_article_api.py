import requests
import json

article_id = "6105d965-a735-479e-a61c-da3276729e3a"
url = f"http://localhost:8000/api/publish"

payload = {
    "article_id": article_id,
    "dry_run": False
}

try:
    print(f"Tentando publicar artigo {article_id}...")
    r = requests.post(url, json=payload)
    print(f"Status Code: {r.status_code}")
    print(f"Response: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")
except Exception as e:
    print(f"Erro ao chamar API: {e}")
