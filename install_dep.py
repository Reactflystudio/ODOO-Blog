
import subprocess
import sys

print("Installing python-multipart...")
process = subprocess.run(
    [sys.executable, "-m", "pip", "install", "python-multipart"],
    capture_output=True,
    text=True
)
print("STDOUT:", process.stdout)
print("STDERR:", process.stderr)
print("Return code:", process.returncode)
