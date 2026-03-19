import sys
try:
    from web.server import app, discover_trends
    print("Imports OK")
except Exception as e:
    print(f"Error importing app: {e}")
