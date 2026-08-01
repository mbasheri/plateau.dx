#!/usr/bin/env bash
# Local full-stack dev runner (Postgres-backed, mirrors the Vercel routing).
# Needs DATABASE_URL pointing at a Postgres database (e.g. a free Neon dev branch).
#   export DATABASE_URL="postgres://…/neondb?sslmode=require"
#   ./run.sh
# Production runs on Vercel — see DEPLOY.md.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating virtualenv + installing dependencies..."
  python3 -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip >/dev/null
fi
# Always ensure deps are present (uses python -m pip so a moved venv still works).
./.venv/bin/python -m pip install -q -r requirements.txt

if [ -z "${DATABASE_URL:-}" ] && [ -z "${POSTGRES_URL:-}" ]; then
  echo "ERROR: set DATABASE_URL (or POSTGRES_URL) to your Postgres connection string." >&2
  echo "       e.g. export DATABASE_URL=\"postgres://…/neondb?sslmode=require\"" >&2
  exit 1
fi

echo "Seeding database (idempotent)…"
./.venv/bin/python -m server.seed

echo "Starting on http://127.0.0.1:8000  (Ctrl-C to stop)"
exec ./.venv/bin/python -m uvicorn server.local:app --port 8000 --reload
