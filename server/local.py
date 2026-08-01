"""
local.py — LOCAL full-stack dev server (not used in production).

On Vercel, static files are served by Vercel and /api/* by the function. To get
the same single-origin experience locally, this wraps the API `app` with the
static frontend + the two HTML routes, mirroring the root vercel.json.

Run (needs DATABASE_URL pointing at your Postgres, e.g. a Neon dev branch):

    DATABASE_URL="postgres://..." \
      ./.venv/bin/python -m uvicorn server.local:app --port 8000 --reload

Seed the database once first:  DATABASE_URL="..." python -m server.seed
"""

from __future__ import annotations

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.main import ROOT, app

WEB_DIR = ROOT / "web"

app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def landing():
    return FileResponse(str(WEB_DIR / "landing.html"))


@app.get("/app")
def dashboard():
    return FileResponse(str(WEB_DIR / "index.html"))
