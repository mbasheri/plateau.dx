"""
scripts/e2e_pg.py — end-to-end smoke test of the API against a throwaway Postgres.

No external database needed: it boots a self-contained Postgres (pgserver),
creates the schema, seeds the demo data, then hits every endpoint via FastAPI's
TestClient and checks the responses. Great for validating the Postgres data
layer before deploying.

    ./.venv/bin/python -m pip install pgserver httpx
    ./.venv/bin/python scripts/e2e_pg.py
"""

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pgserver  # noqa: E402

pgdata = ROOT / ".pg-e2e"
pgdata.mkdir(exist_ok=True)
print("Starting a throwaway Postgres…")
server = pgserver.get_server(pgdata)
os.environ["DATABASE_URL"] = server.get_uri()

fails = []


def check(label, cond, extra=""):
    print(("  ok   " if cond else " FAIL  ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        fails.append(label)


try:
    from server.db import init_db
    from server.seed import bootstrap_seed
    init_db()
    bootstrap_seed()
    print("Schema created + demo seeded.\n")

    from fastapi.testclient import TestClient
    from server.main import app
    c = TestClient(app)

    b = c.get("/api/bootstrap").json()
    check("bootstrap: demo user", b["user"]["display_name"] == "Demo Athlete")
    check("bootstrap: library seeded", len(b["exercises"]) > 50, f"n={len(b['exercises'])}")
    check("bootstrap: has routine", b["has_routine"] is True)

    s = c.get("/api/summary").json()
    check("summary: 21 sleep points", len(s["sleep"]) == 21)
    check("summary: calories", s["calories"]["eaten"] > 0 and s["calories"]["burned"] > 0)

    d = c.get("/api/diagnose").json()
    named = {r["exercise"]["name"]: (r["causes"][0]["id"] if r["causes"] else None)
             for r in d["reports"]}
    check("diagnose: Bench -> fatigue", named.get("Bench Press") == "fatigue")
    check("diagnose: OHP -> insufficient", named.get("Overhead Press") == "insufficient_stimulus")
    check("diagnose: Row -> stale", named.get("Barbell Row") == "programming_staleness")
    check("diagnose: Squat progressing", named.get("Back Squat") is None)

    rt = c.get("/api/routine").json()
    check("routine: Upper/Lower, 4 days", rt and rt["name"] == "Upper / Lower" and len(rt["days"]) == 4)
    check("templates: >=5", len(c.get("/api/templates").json()) >= 5)
    check("template detail", bool(c.get("/api/templates/upper-lower").json()["days"]))
    check("next-day", "exercises" in (c.get("/api/routine/next-day").json() or {}))
    check("search (ILIKE)", any("Bench" in e["name"] for e in c.get("/api/exercises?q=bench").json()))

    check("checkin upsert", c.post("/api/checkins", json={"date": "2020-01-01",
          "sleep_hours": 8, "stress": 2}).json().get("ok") is True)
    sid = c.post("/api/sessions", json={"date": "2020-01-02", "sets": [
        {"exercise_name": "Bench Press", "reps": 5, "weight": 165, "rpe": 8}]}).json()
    check("log session (RETURNING id)", isinstance(sid.get("id"), int))
    check("save routine (new version)", c.put("/api/routine", json={"name": "Test", "days": [
        {"label": "A", "exercises": [{"exercise_id": b["exercises"][0]["id"],
         "target_sets": 3, "target_rep_low": 5, "target_rep_high": 8}]}]}).status_code == 200)

    print("\n" + ("ALL GOOD" if not fails else f"FAILURES: {fails}"))
finally:
    server.cleanup()

sys.exit(1 if fails else 0)
