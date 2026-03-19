import subprocess
import os

try:
    process = subprocess.Popen(
        ["python", "-m", "uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=os.path.abspath("odoo_blog_ai_system")
    )
    # Wait a bit or communicate
    try:
        stdout, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        
    with open("python_start_log.txt", "w", encoding="utf-8") as f:
        f.write("STDOUT:\n" + stdout + "\nSTDERR:\n" + stderr)

except Exception as e:
    with open("python_start_log.txt", "w", encoding="utf-8") as f:
        f.write("EXCEPTION: " + str(e))
