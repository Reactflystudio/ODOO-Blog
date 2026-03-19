import requests
try:
    r = requests.post("http://localhost:8000/api/config/reload")
    print(r.json())
except Exception as e:
    print(e)
