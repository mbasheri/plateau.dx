"""
seed.py — reference data + a realistic demo athlete.

Two independent, idempotent steps (both safe to run every startup):

  1. seed_reference_data() — ensures the exercise LIBRARY and split TEMPLATES
     exist. On an upgraded DB it MERGES any pre-existing lifts (matched by name)
     into the global catalog, preserving their ids so old workout_sets stay valid.

  2. seed_demo_if_empty() + ensure_demo_routine() — on a fresh DB, create the demo
     athlete: ~7 weeks of ~2x/week training plus daily check-ins, and an active
     Upper/Lower routine (backdated ~8 weeks so it reads as unchanged).

The demo tells ONE coherent story (recent overreaching) that still yields three
different diagnoses once the routine is attached:
  * Bench Press    -> FATIGUE (recovery craters in weeks 5-6 while RPE climbs).
  * Overhead Press -> INSUFFICIENT STIMULUS (plans 4 sets, logs 3; easy RPE).
  * Barbell Row    -> STALE PROGRAMMING (routine unchanged; back trained with a
                      single movement pattern — only rows).
  * Back Squat / Deadlift -> still PROGRESSING.
"""

from __future__ import annotations

from datetime import date, timedelta

from server import repository as repo
from server.db import connect, init_db
from server.library import LIBRARY, TEMPLATES

WEEKS = 7
# Anchor the demo so the most recent check-in lands on TODAY — the dashboard's
# sleep chart and today's calorie ring always read as current, and the plateaus
# stay "recent" no matter when the app is first run.
START = date.today() - timedelta(days=WEEKS * 7 - 1)
# Global weekly lifestyle trend; recovery craters in weeks 5-6.
SLEEP_BY_WEEK = [7.5, 7.4, 7.3, 7.2, 6.9, 5.6, 5.0]
STRESS_BY_WEEK = [2, 2, 3, 3, 3, 4, 5]
# Maintenance-ish calories eaten per day (the engine ignores this column; it
# feeds only the dashboard's calorie ring). A gentle intra-week wave looks real.
BASE_CALORIES = 2700

# Demo workouts by exercise slug: (weekday offsets, [(weight, reps, rpe), ...]).
# Two offsets => ~2x/week; one => ~1x/week. 3 identical working sets each.
WORKOUTS = {
    # Progresses to 160, then stalls 8 sessions while RPE climbs -> fatigue.
    "bench-press": ([0, 3],
        [(135 + 5 * i, 5, r) for i, r in enumerate([7, 7, 7.5, 7.5, 8, 8])]
        + [(160, 5, r) for r in [8, 8.5, 8.5, 9, 9, 9, 9.5, 9.5]]),
    # Adds weight all block -> progressing.
    "back-squat": ([1, 4], [(185 + 5 * i, 5, 7.5 if i < 7 else 8.0)
                            for i in range(14)]),
    # Once a week, climbing -> progressing.
    "deadlift": ([2], [(255 + 10 * i, 3, 7.0 if i < 4 else 7.5) for i in range(7)]),
    # Stuck at 95x8, easy (RPE 6), logged in the rested early weeks -> insufficient.
    "overhead-press": ([2, 5], [(95, 8, 6.0) for _ in range(8)]),
    # Identical 3x10 for ~4.5 weeks -> stale.
    "barbell-row": ([0, 3], [(95, 10, 7.5) for _ in range(10)]),
}

# The demo's active routine (Upper/Lower, 4 sessions/week). Composition is chosen
# so the three diagnoses stay clean: chest & shoulders each get 2 movement
# patterns (no staleness), back gets only the row (1 pattern -> staleness), and
# OHP's target (4) exceeds what's logged (3) -> measurable insufficient stimulus.
# Rows: (exercise_slug, target_sets, rep_low, rep_high).
DEMO_ROUTINE_DAYS = [
    ("Upper A", [
        ("bench-press", 3, 5, 8), ("barbell-row", 3, 6, 10),
        ("overhead-press", 4, 6, 10), ("incline-dumbbell-press", 3, 8, 12),
        ("lateral-raise", 3, 12, 20),
    ]),
    ("Upper B", [
        ("bench-press", 3, 5, 8), ("barbell-row", 3, 6, 10),
        ("overhead-press", 4, 6, 10), ("lateral-raise", 3, 12, 20),
    ]),
    ("Lower A", [
        ("back-squat", 3, 5, 8), ("deadlift", 3, 3, 5),
        ("leg-press", 3, 10, 15), ("lying-leg-curl", 3, 10, 15),
    ]),
    ("Lower B", [
        ("back-squat", 3, 5, 8), ("romanian-deadlift", 3, 6, 10),
        ("leg-extension", 3, 12, 15), ("standing-calf-raise", 4, 10, 15),
    ]),
]


def bootstrap_seed() -> None:
    """Run all seeding steps once at startup (each is idempotent)."""
    conn = connect()
    try:
        seed_reference_data(conn)
        seed_demo_if_empty(conn)
        ensure_demo_routine(conn)
    finally:
        conn.close()


def seed_reference_data(conn) -> None:
    """Ensure the global library + templates exist; merge pre-existing lifts."""
    for slug, name, mg, mp, eq, compound in LIBRARY:
        row = conn.execute(
            "SELECT id FROM exercises WHERE slug=? OR lower(name)=lower(?) LIMIT 1",
            (slug, name),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE exercises SET user_id=NULL, slug=?, muscle_group=?, "
                "movement_pattern=?, equipment=?, is_compound=? WHERE id=?",
                (slug, mg, mp, eq, 1 if compound else 0, row["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO exercises (user_id, slug, name, muscle_group, "
                "movement_pattern, equipment, is_compound) "
                "VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                (slug, name, mg, mp, eq, 1 if compound else 0),
            )

    for key, tpl in TEMPLATES.items():
        if conn.execute("SELECT 1 FROM split_templates WHERE key=?",
                        (key,)).fetchone():
            continue
        cur = conn.execute(
            "INSERT INTO split_templates (user_id, key, name, description, num_days) "
            "VALUES (NULL, ?, ?, ?, ?) RETURNING id",
            (key, tpl["name"], tpl["description"], len(tpl["days"])),
        )
        tid = cur.fetchone()["id"]
        for di, (label, exs) in enumerate(tpl["days"]):
            dcur = conn.execute(
                "INSERT INTO split_template_days (template_id, day_index, label) "
                "VALUES (?, ?, ?) RETURNING id", (tid, di, label))
            did = dcur.fetchone()["id"]
            for oi, (eslug, sets, rl, rh) in enumerate(exs):
                conn.execute(
                    "INSERT INTO split_template_day_exercises "
                    "(template_day_id, exercise_slug, display_order, target_sets, "
                    " target_rep_low, target_rep_high) VALUES (?, ?, ?, ?, ?, ?)",
                    (did, eslug, oi, sets, rl, rh))
    conn.commit()


def _eid(conn, slug):
    row = conn.execute("SELECT id FROM exercises WHERE slug=?", (slug,)).fetchone()
    return row["id"] if row else None


def seed_demo_if_empty(conn) -> None:
    """Create the demo user + workouts + check-ins only if there are no users."""
    if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]:
        return
    conn.execute(
        "INSERT INTO users (id, display_name, weight_unit, goal) "
        "VALUES (1, 'Demo Athlete', 'lb', 'strength')"
    )

    for slug, (offsets, plan) in WORKOUTS.items():
        ex_id = _eid(conn, slug)
        per = len(offsets)
        for i, (weight, reps, rpe) in enumerate(plan):
            week, off = i // per, offsets[i % per]
            day = (START + timedelta(days=week * 7 + off)).isoformat()
            scur = conn.execute(
                "INSERT INTO workout_sessions (user_id, date) VALUES (1, ?) "
                "RETURNING id",
                (day,))
            sid = scur.fetchone()["id"]
            for set_no in range(1, 4):
                conn.execute(
                    "INSERT INTO workout_sets (session_id, exercise_id, "
                    "set_number, reps, weight, rpe) VALUES (?, ?, ?, ?, ?, ?)",
                    (sid, ex_id, set_no, reps, weight, rpe))

    for d in range(WEEKS * 7):
        day = (START + timedelta(days=d)).isoformat()
        week = d // 7
        calories = BASE_CALORIES + ((d % 7) - 3) * 45  # ~2565–2880, deterministic
        conn.execute(
            "INSERT INTO daily_checkins (user_id, date, sleep_hours, stress, "
            "body_weight, nutrition, calories) VALUES (1, ?, ?, ?, ?, 'enough', ?)",
            (day, SLEEP_BY_WEEK[week], STRESS_BY_WEEK[week], 180.0, calories))
    conn.commit()


def ensure_demo_routine(conn) -> None:
    """Attach the demo Upper/Lower routine if the demo user has none yet."""
    if not conn.execute("SELECT 1 FROM users WHERE id=1").fetchone():
        return
    if repo.get_active_routine(conn, 1):
        return

    days = []
    for label, exs in DEMO_ROUTINE_DAYS:
        exl = []
        for slug, sets, rl, rh in exs:
            eid = _eid(conn, slug)
            if eid:
                exl.append({"exercise_id": eid, "target_sets": sets,
                            "target_rep_low": rl, "target_rep_high": rh})
        days.append({"label": label, "exercises": exl})

    # Backdate so the routine reads as unchanged for ~8 weeks (staleness signal).
    backdated = (date.today() - timedelta(weeks=8)).isoformat() + " 00:00:00"
    repo.save_routine(conn, 1, "Upper / Lower", days,
                      source_template_key="upper-lower", changed_at=backdated)


if __name__ == "__main__":
    # One-off setup: create the schema (idempotent) then seed. Run once against
    # your Postgres database — this replaces the old serverless-incompatible
    # startup hook:  DATABASE_URL="postgres://..." python -m server.seed
    init_db()
    bootstrap_seed()
    print("Schema created and demo data seeded.")
