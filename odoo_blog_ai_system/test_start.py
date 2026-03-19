
import subprocess
import sys
import time
import os

print("Starting server test...")
with open("manual_start.log", "w") as f:
    p = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web.server:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=f,
        stderr=f,
        cwd=os.getcwd()
    )
    time.sleep(5)
    print(f"Server process PID: {p.pid}")
    if p.poll() is None:
        print("Server still running after 5 seconds.")
    else:
        print(f"Server exited with code {p.returncode}")
