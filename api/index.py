"""
api/index.py — Vercel serverless entry point.

Vercel's Python runtime serves the exposed ASGI `app`. The root vercel.json
rewrites every /api/* request to this function, and FastAPI (in server/main.py)
routes on the original path (/api/bootstrap, /api/diagnose, ...). The engine and
data layer are imported unchanged — only *where* the HTTP layer runs has moved.
"""

import pathlib
import sys

# Ensure the repo root is importable so `server` and `engine` resolve when Vercel
# loads this function.
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.main import app  # noqa: E402,F401  (Vercel serves this ASGI `app`)
