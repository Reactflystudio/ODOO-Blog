
import subprocess
import sys

with open("install_dep_output.txt", "w") as f:
    f.write("Installing python-multipart...\n")
    try:
        process = subprocess.run(
            [sys.executable, "-m", "pip", "install", "python-multipart"],
            capture_output=True,
            text=True
        )
        f.write(f"STDOUT:\n{process.stdout}\n")
        f.write(f"STDERR:\n{process.stderr}\n")
        f.write(f"Return code: {process.returncode}\n")
    except Exception as e:
        f.write(f"Exception: {e}\n")
