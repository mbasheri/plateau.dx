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
from typing import Optional

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
from server.schemas import (  # noqa: E402
    CheckinIn, ExerciseIn, RoutineIn, SessionIn, UserIn,
)
from server.seed import bootstrap_seed  # noqa: E402

USER_ID = 1
WEB_DIR = ROOT / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bootstrap_seed()
    yield


app = FastAPI(title="Plateau·Dx", lifespan=lifespan)


# ==========================================================================
# Bootstrap / user
# ==========================================================================

@app.get("/api/bootstrap")
def bootstrap(conn=Depends(get_db)):
    user = repo.get_user(conn, USER_ID)
    return {
        "user": dict(user) if user else None,
        "exercises": [dict(r) for r in repo.list_exercises(conn, USER_ID)],
        "has_routine": repo.get_active_routine(conn, USER_ID) is not None,
    }


@app.put("/api/user")
def put_user(body: UserIn, conn=Depends(get_db)):
    repo.update_user(conn, USER_ID, body.display_name, body.weight_unit, body.goal)
    return dict(repo.get_user(conn, USER_ID))


# ==========================================================================
# Exercise library
# ==========================================================================

@app.get("/api/exercises")
def get_exercises(q: Optional[str] = None, muscle_group: Optional[str] = None,
                  equipment: Optional[str] = None, conn=Depends(get_db)):
    return repo.search_exercises(conn, USER_ID, q, muscle_group, equipment)


@app.post("/api/exercises")
def post_exercise(body: ExerciseIn, conn=Depends(get_db)):
    row = repo.ensure_exercise(conn, USER_ID, body.name, body.muscle_group,
                               body.equipment, body.movement_pattern)
    return dict(row)


# ==========================================================================
# Split templates + routine
# ==========================================================================

@app.get("/api/templates")
def get_templates(conn=Depends(get_db)):
    return repo.list_templates(conn)


@app.get("/api/templates/{key}")
def get_template(key: str, conn=Depends(get_db)):
    tpl = repo.get_template_full(conn, key)
    if not tpl:
        raise HTTPException(404, "template not found")
    return tpl


@app.get("/api/routine")
def get_routine(conn=Depends(get_db)):
    return repo.get_routine_full(conn, USER_ID)  # may be null


@app.put("/api/routine")
def put_routine(body: RoutineIn, conn=Depends(get_db)):
    days = [d.model_dump() for d in body.days]
    repo.save_routine(conn, USER_ID, body.name, days, body.source_template_key)
    return repo.get_routine_full(conn, USER_ID)


@app.post("/api/routine/from-template/{key}")
def post_routine_from_template(key: str, conn=Depends(get_db)):
    rid = repo.routine_from_template(conn, USER_ID, key)
    if rid is None:
        raise HTTPException(404, "template not found")
    return repo.get_routine_full(conn, USER_ID)


@app.get("/api/routine/next-day")
def get_next_day(conn=Depends(get_db)):
    return repo.suggest_next_day(conn, USER_ID)  # may be null


# ==========================================================================
# Sessions + check-ins
# ==========================================================================

@app.post("/api/sessions")
def post_session(body: SessionIn, conn=Depends(get_db)):
    sets = [s.model_dump() for s in body.sets]
    for s in sets:
        if not s.get("exercise_id") and not s.get("exercise_name"):
            raise HTTPException(422, "each set needs exercise_id or exercise_name")
    session_id = repo.create_session(conn, USER_ID, body.date.isoformat(),
                                     body.notes, sets, body.routine_day_id)
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


# ==========================================================================
# Diagnosis
# ==========================================================================

@app.get("/api/diagnose")
def get_diagnose(conn=Depends(get_db)):
    """
    Run the engine across every exercise with logged sets, feeding each its
    RoutineContext (target sets, declared frequency, routine age, pattern count)
    when the user has an active routine. Persists the latest verdict per exercise.
    """
    user = repo.get_user(conn, USER_ID)
    goal = user["goal"] if user else "strength"
    contexts = repo.load_contexts(conn, USER_ID)

    reports = []
    for ex in repo.exercises_with_sessions(conn, USER_ID):
        info = repo.exercise_info(ex)
        sessions = repo.load_exercise_sessions(conn, USER_ID, ex["id"])
        routine_ctx = repo.routine_context_for(conn, USER_ID, ex)
        report = diagnose_exercise(info, sessions, contexts, goal=goal,
                                   routine=routine_ctx)
        payload = to_serializable(report)
        repo.save_report(conn, USER_ID, ex["id"], payload)
        reports.append(payload)

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
def landing():
    """Marketing landing page (separate register from the dashboard)."""
    return FileResponse(str(WEB_DIR / "landing.html"))


@app.get("/app")
def dashboard():
    """The dashboard single-page app."""
    return FileResponse(str(WEB_DIR / "index.html"))
