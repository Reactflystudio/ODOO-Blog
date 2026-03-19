"""Kill process on port 8000 and restart the server."""
import subprocess
import sys
import os

# Find and kill processes on port 8000
result = subprocess.run(
    ['netstat', '-ano'], capture_output=True, text=True
)

pids_to_kill = set()
for line in result.stdout.splitlines():
    if ':8000' in line and 'LISTENING' in line:
        parts = line.strip().split()
        if parts:
            try:
                pid = int(parts[-1])
                pids_to_kill.add(pid)
            except ValueError:
                pass

for pid in pids_to_kill:
    print(f"Killing PID {pid}...")
    try:
        subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
    except Exception as e:
        print(f"  Error: {e}")

if pids_to_kill:
    print(f"Killed {len(pids_to_kill)} process(es)")
    import time
    time.sleep(2)
else:
    print("No processes found on port 8000")

# Test .env reading
sys.path.insert(0, os.path.dirname(__file__))
from config import Settings
s = Settings()
print(f"\nConfig from .env:")
print(f"  default_llm_provider = {s.default_llm_provider}")
print(f"  google_ai_api_key = {s.google_ai_api_key[:15]}..." if s.google_ai_api_key else "  google_ai_api_key = EMPTY")
print(f"  gemini_model = {s.gemini_model}")

# Start server
print("\nStarting uvicorn server...")
os.chdir(os.path.dirname(__file__))
subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'web.server:app', '--reload', '--host', '127.0.0.1', '--port', '8000'],
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
)
print("Server started! Access at http://localhost:8000")
