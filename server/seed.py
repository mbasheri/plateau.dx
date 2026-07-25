"""
seed.py — realistic demo data so the dashboard and engine are visibly working on
first run (and so you have something to eyeball while tuning thresholds).

The story is ONE coherent athlete training each lift ~2x/week over ~7 weeks.
Lifestyle inputs (sleep, stress) are GLOBAL per day — as in real life — so the
demo is built around a single plausible timeline: solid training, then ~2 weeks
of overreaching (sleep falling, stress rising in weeks 5-6). Under that one
timeline it still showcases three different diagnoses plus two healthy lifts:

  * Bench Press      -> FATIGUE plateau (the headline; matches the spec example):
                        stuck at 160 while RPE climbs toward 9.5 and, in the last
                        two weeks, sleep craters and stress spikes.
  * Overhead Press   -> INSUFFICIENT STIMULUS: stalled but easy (RPE 6), and only
                        trained in the earlier well-rested weeks, so recovery
                        isn't the issue.
  * Barbell Row      -> STALE PROGRAMMING: identical 3x10 @ 95 for ~4+ weeks,
                        finished before the fatigue window.
  * Back Squat       -> still PROGRESSING (healthy contrast — the app shouldn't
                        cry wolf on a lift that's clearly advancing).
  * Deadlift         -> still PROGRESSING (trained once a week).

Tuned to match the default thresholds (plateau window 5 sessions, >=6 to judge).
Nutrition/technique causes aren't in the demo headline but are covered by tests.
"""

from __future__ import annotations

from datetime import date, timedelta

from server.db import connect

# Week 0 anchor. ~7 weeks of history ending mid-July 2026 (recent "today").
START = date(2026, 6, 1)

# GLOBAL weekly lifestyle trend (index = week 0..6). Recovery craters in wks 5-6.
SLEEP_BY_WEEK = [7.5, 7.4, 7.3, 7.2, 7.0, 5.8, 5.4]
STRESS_BY_WEEK = [2, 2, 3, 3, 3, 4, 5]
WEEKS = len(SLEEP_BY_WEEK)

# Exercise catalog: name -> (muscle_group, modality, weekday offsets per week).
# Two offsets => trained ~2x/week; one offset => ~1x/week.
EXERCISES = {
    "Bench Press":    ("chest",     "barbell", [0, 3]),
    "Back Squat":     ("quads",     "barbell", [1, 4]),
    "Deadlift":       ("back",      "barbell", [2]),
    "Overhead Press": ("shoulders", "barbell", [2, 5]),
    "Barbell Row":    ("back",      "barbell", [0, 3]),
}

# Training plans: exercise -> list of (weight, reps, rpe), one per session in
# order. Each entry is performed as 3 identical working sets.
PLANS = {
    # 6 sessions of progress to 160, then 8 sessions stuck at 160 with RPE
    # climbing — the classic fatigue signature, worsened by the wks 5-6 dip.
    "Bench Press": (
        [(135 + 5 * i, 5, r) for i, r in enumerate([7, 7, 7.5, 7.5, 8, 8])]
        + [(160, 5, r) for r in [8, 8.5, 8.5, 9, 9, 9, 9.5, 9.5]]
    ),
    # Adds weight every session for the whole block -> no plateau.
    "Back Squat": [(185 + 5 * i, 5, 7.5 if i < 7 else 8.0) for i in range(14)],
    # Once a week, still climbing -> no plateau.
    "Deadlift": [(255 + 10 * i, 3, 7.0 if i < 4 else 7.5) for i in range(7)],
    # Stuck at 95x8, but RPE is only 6 and it was logged in the rested weeks 0-3.
    "Overhead Press": [(95, 8, 6.0) for _ in range(8)],
    # The exact same 3x10 @ 95 for ~4.5 weeks (weeks 0-4) -> stale.
    "Barbell Row": [(95, 10, 7.5) for _ in range(10)],
}


def _session_date(index: int, offsets) -> date:
    """Date of the i-th session given this lift's weekly offsets."""
    per = len(offsets)
    week = index // per
    return START + timedelta(days=week * 7 + offsets[index % per])


def seed_if_empty() -> None:
    """Populate demo data only if the database has no users yet."""
    conn = connect()
    try:
        if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]:
            return
        _seed(conn)
    finally:
        conn.close()


def _seed(conn) -> None:
    # --- user ---
    conn.execute(
        "INSERT INTO users (id, display_name, weight_unit, goal) "
        "VALUES (1, 'Demo Athlete', 'lb', 'strength')"
    )

    # --- exercises ---
    ex_id = {}
    for name, (muscle, modality, _offsets) in EXERCISES.items():
        cur = conn.execute(
            "INSERT INTO exercises (user_id, name, muscle_group, modality) "
            "VALUES (1, ?, ?, ?)",
            (name, muscle, modality),
        )
        ex_id[name] = cur.lastrowid

    # --- workouts (one session per exercise per date) ---
    for name, plan in PLANS.items():
        _muscle, _mod, offsets = EXERCISES[name]
        for index, (weight, reps, rpe) in enumerate(plan):
            day = _session_date(index, offsets).isoformat()
            cur = conn.execute(
                "INSERT INTO workout_sessions (user_id, date) VALUES (1, ?)",
                (day,),
            )
            session_id = cur.lastrowid
            for set_no in range(1, 4):  # 3 identical working sets
                conn.execute(
                    "INSERT INTO workout_sets "
                    "(session_id, exercise_id, set_number, reps, weight, rpe) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, ex_id[name], set_no, reps, weight, rpe),
                )

    # --- daily check-ins for every day in the block ---
    for d in range(WEEKS * 7):
        day = (START + timedelta(days=d)).isoformat()
        week = d // 7
        conn.execute(
            "INSERT INTO daily_checkins "
            "(user_id, date, sleep_hours, stress, body_weight, nutrition) "
            "VALUES (1, ?, ?, ?, ?, 'enough')",
            (day, SLEEP_BY_WEEK[week], STRESS_BY_WEEK[week], 180.0),
        )

    conn.commit()
