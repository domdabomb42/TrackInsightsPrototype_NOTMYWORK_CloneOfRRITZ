"""Vercel entrypoint; keep the existing web/wsgi.py for local development."""
import sys
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent / "web"
sys.path.insert(0, str(WEB_ROOT))

from app import create_app  # noqa: E402

app = create_app()
