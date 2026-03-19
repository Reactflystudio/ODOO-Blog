@echo off
cd odoo_blog_ai_system
python -m uvicorn web.server:app --reload --host 0.0.0.0 --port 8000
pause
