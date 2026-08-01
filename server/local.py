"""
local.py — LOCAL full-stack dev server (not used in production).

On Vercel, static files live in public/ (served at the root) and /api/* is the
function. To get the same single-origin experience locally, this wraps the API
`app` with those static files + the two HTML routes, mirroring the root
vercel.json (/ -> public/index.html [landing], /app -> public/app.html
[dashboard], /static/* -> public/*).

Run (needs DATABASE_URL pointing at your Postgres, e.g. a Neon dev branch):

    DATABASE_URL="postgres://..." \
      ./.venv/bin/python -m uvicorn server.local:app --port 8000 --reload

Seed the database once first:  DATABASE_URL="..." python -m server.seed
"""

from __future__ import annotations

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.main import ROOT, app

PUBLIC_DIR = ROOT / "public"

# The frontend references assets under /static/*; on Vercel a rewrite maps those
# to public/*. Locally we mount public/ at /static to match.
app.mount("/static", StaticFiles(directory=str(PUBLIC_DIR)), name="static")


@app.get("/")
def landing():
    return FileResponse(str(PUBLIC_DIR / "index.html"))


@app.get("/app")
def dashboard():
    return FileResponse(str(PUBLIC_DIR / "app.html"))
