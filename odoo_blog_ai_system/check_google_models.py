import httpx
import json

api_key = "AIzaSyC5rz4mmdYSSu0cZGXbzm87J7eIi88aR44"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

def check_models():
    r = httpx.get(url)
    print(f"Status: {r.status_code}")
    data = r.json()
    for m in data.get("models", []):
        if "imagen" in m["name"].lower():
            print(f"Model: {m['name']}")

if __name__ == "__main__":
    check_models()
