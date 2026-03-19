import requests
import json

payload = {
    "count": 1,
    "topics": ["Como trabalhar com SEO e Marketing"],
    "article_type": "guia",
    "primary_keyword": "politica local",
    "secondary_keywords": [],
    "tone": "didatico",
    "depth": "intermediate",
    "min_chars": 500,
    "max_chars": 1500,
    "audiences": ["politicos"],
    "min_images": 0,
    "max_images": 0,
    "provider": "gemini",
    "faq_min": 1,
    "faq_max": 2,
    "share_buttons": []
}

try:
    print("Enviando request...")
    r = requests.post("http://localhost:8000/api/generate/empurrao", json=payload, timeout=600)
    print("Status:", r.status_code)
    try:
        resp = r.json()
        print("Success:", resp.get("success"))
        print("Erro:", resp.get("detail"))
        print("---")
        if resp.get("articles"):
            html = resp["articles"][0].get("content_html_full") or resp["articles"][0].get("content_html")
            print("Preview HTML:")
            print(html[:500])
    except:
        print("Raw text:", r.text[:500])
except Exception as e:
    print("Failed:", str(e))
