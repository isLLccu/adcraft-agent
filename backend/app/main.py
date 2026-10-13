"""v2 入口：python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"""
from app.ai.api import create_app

app = create_app()
