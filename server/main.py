"""
main.py — FastAPI application: JSON API under /api + the static React frontend.

Run from the project root:
    ./.venv/bin/python -m uvicorn server.main:app --reload --port 8000

Single-user MVP: every route operates on USER_ID. The user_id columns and this
constant are the only things that would change to go multi-tenant — the schema
and engine already carry the concept.
"""

from __future__ import annotations

import pathlib
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# Make the project root importable so `import engine` works no matter where
# uvicorn is launched from.
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import Depends, FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from engine import diagnose_exercise, to_serializable  # noqa: E402
from server import repository as repo  # noqa: E402
from server.db import get_db, init_db  # noqa: E402
from server.schemas import CheckinIn, ExerciseIn, SessionIn, UserIn  # noqa: E402
from server.seed import seed_if_empty  # noqa: E402

# The single local user for the MVP (see module docstring).
USER_ID = 1

WEB_DIR = ROOT / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_if_empty()
    yield


app = FastAPI(title="Plateau Diagnosis Fitness Tracker", lifespan=lifespan)


# ==========================================================================
# API
# ==========================================================================

@app.get("/api/bootstrap")
def bootstrap(conn=Depends(get_db)):
    """Everything the UI needs on first load."""
    user = repo.get_user(conn, USER_ID)
    exercises = [dict(r) for r in repo.list_exercises(conn, USER_ID)]
    return {
        "user": dict(user) if user else None,
        "exercises": exercises,
    }


@app.put("/api/user")
def put_user(body: UserIn, conn=Depends(get_db)):
    repo.update_user(conn, USER_ID, body.display_name, body.weight_unit, body.goal)
    return dict(repo.get_user(conn, USER_ID))


@app.get("/api/exercises")
def get_exercises(conn=Depends(get_db)):
    return [dict(r) for r in repo.list_exercises(conn, USER_ID)]


@app.post("/api/exercises")
def post_exercise(body: ExerciseIn, conn=Depends(get_db)):
    row = repo.ensure_exercise(conn, USER_ID, body.name,
                               body.muscle_group, body.modality)
    return dict(row)


@app.post("/api/sessions")
def post_session(body: SessionIn, conn=Depends(get_db)):
    sets = [s.model_dump() for s in body.sets]
    for s in sets:
        if not s.get("exercise_id") and not s.get("exercise_name"):
            raise HTTPException(422, "each set needs exercise_id or exercise_name")
    session_id = repo.create_session(
        conn, USER_ID, body.date.isoformat(), body.notes, sets
    )
    return {"id": session_id}


@app.get("/api/sessions")
def get_sessions(conn=Depends(get_db)):
    return repo.list_sessions(conn, USER_ID)


@app.post("/api/checkins")
def post_checkin(body: CheckinIn, conn=Depends(get_db)):
    repo.upsert_checkin(
        conn, USER_ID, body.date.isoformat(),
        sleep_hours=body.sleep_hours, stress=body.stress,
        body_weight=body.body_weight, nutrition=body.nutrition,
        calories=body.calories, notes=body.notes,
    )
    return {"ok": True}


@app.get("/api/checkins")
def get_checkins(conn=Depends(get_db)):
    return repo.list_checkins(conn, USER_ID)


@app.get("/api/diagnose")
def get_diagnose(conn=Depends(get_db)):
    """
    Run the engine across every exercise that has logged sets, persist the latest
    verdict per exercise, and return the full reports (each carries its own metric
    series for charting and its ranked causes with evidence).
    """
    user = repo.get_user(conn, USER_ID)
    goal = user["goal"] if user else "strength"
    contexts = repo.load_contexts(conn, USER_ID)

    reports = []
    for ex in repo.exercises_with_sessions(conn, USER_ID):
        info = repo.exercise_info(ex)
        sessions = repo.load_exercise_sessions(conn, USER_ID, ex["id"])
        report = diagnose_exercise(info, sessions, contexts, goal=goal)
        payload = to_serializable(report)
        repo.save_report(conn, USER_ID, ex["id"], payload)
        reports.append(payload)

    # Most actionable first: real plateaus, then still-progressing / low-data.
    reports.sort(key=lambda r: (not r["plateau"]["is_plateau"],
                                r["exercise"]["name"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "goal": goal,
        "reports": reports,
    }


# ==========================================================================
# Static frontend (mounted last so it never shadows /api routes)
# ==========================================================================

app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(WEB_DIR / "index.html"))
