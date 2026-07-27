#!/usr/bin/env bash
# One-shot dev runner: sets up the venv on first run, then starts the app.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating virtualenv + installing dependencies..."
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip >/dev/null
  ./.venv/bin/pip install -r requirements.txt
fi

echo "Starting on http://127.0.0.1:8000  (Ctrl-C to stop)"
exec ./.venv/bin/python -m uvicorn server.main:app --port 8000 --reload
