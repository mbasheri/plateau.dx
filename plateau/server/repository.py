"""
repository.py — all SQL, plus the mapping from DB rows to the engine's input
dataclasses (including the new RoutineContext).

This is the ONLY layer that knows both SQLite and the engine. Route handlers call
these functions; the engine never sees a database row.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional

from engine.types import (
    DailyContext,
    ExerciseInfo,
    ExerciseSession,
    RoutineContext,
    SetLog,
)


# ==========================================================================
# Users
# ==========================================================================

def get_user(conn, user_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def update_user(conn, user_id: int, display_name, weight_unit, goal) -> None:
    conn.execute(
        "UPDATE users SET display_name=?, weight_unit=?, goal=? WHERE id=?",
        (display_name, weight_unit, goal, user_id),
    )
    conn.commit()


# ==========================================================================
# Exercise library (global built-ins + per-user customs)
# ==========================================================================

def list_exercises(conn, user_id: int) -> List[sqlite3.Row]:
    """Every exercise available to the user: global built-ins + their customs."""
    return conn.execute(
        "SELECT * FROM exercises WHERE user_id IS NULL OR user_id = ? "
        "ORDER BY name",
        (user_id,),
    ).fetchall()


def search_exercises(conn, user_id: int, q: Optional[str] = None,
                     muscle_group: Optional[str] = None,
                     equipment: Optional[str] = None) -> List[Dict[str, Any]]:
    """Library search with optional text / muscle_group / equipment filters."""
    sql = ["SELECT * FROM exercises WHERE (user_id IS NULL OR user_id = ?)"]
    args: List[Any] = [user_id]
    if q:
        sql.append("AND name LIKE ?")
        args.append(f"%{q}%")
    if muscle_group:
        sql.append("AND muscle_group = ?")
        args.append(muscle_group)
    if equipment:
        sql.append("AND equipment = ?")
        args.append(equipment)
    sql.append("ORDER BY name")
    return [dict(r) for r in conn.execute(" ".join(sql), args).fetchall()]


def get_exercise(conn, exercise_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM exercises WHERE id = ?",
                        (exercise_id,)).fetchone()


def ensure_exercise(conn, user_id: int, name: str, muscle_group=None,
                    equipment=None, movement_pattern=None) -> sqlite3.Row:
    """
    Return the exercise with this name (global or the user's), creating a
    user-owned custom if it doesn't exist yet. Used when logging an off-plan lift.
    """
    name = name.strip()
    row = conn.execute(
        "SELECT * FROM exercises WHERE (user_id IS NULL OR user_id = ?) "
        "AND name = ? COLLATE NOCASE ORDER BY user_id IS NULL DESC LIMIT 1",
        (user_id, name),
    ).fetchone()
    if row:
        return row
    conn.execute(
        "INSERT INTO exercises (user_id, name, muscle_group, movement_pattern, "
        "equipment, is_compound) VALUES (?, ?, ?, ?, ?, 1)",
        (user_id, name, muscle_group or "other",
         movement_pattern or "other", equipment or "barbell"),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM exercises WHERE user_id = ? AND name = ? COLLATE NOCASE",
        (user_id, name),
    ).fetchone()


def exercises_with_sessions(conn, user_id: int) -> List[sqlite3.Row]:
    """Exercises that have at least one logged set (candidates for diagnosis)."""
    return conn.execute(
        """
        SELECT DISTINCT e.*
        FROM exercises e
        JOIN workout_sets s     ON s.exercise_id = e.id
        JOIN workout_sessions w ON w.id = s.session_id
        WHERE w.user_id = ?
        ORDER BY e.name
        """,
        (user_id,),
    ).fetchall()


def exercise_info(row: sqlite3.Row) -> ExerciseInfo:
    return ExerciseInfo(
        id=row["id"], name=row["name"], muscle_group=row["muscle_group"],
        equipment=row["equipment"], movement_pattern=row["movement_pattern"],
        is_compound=bool(row["is_compound"]),
    )


# ==========================================================================
# Workout sessions + sets
# ==========================================================================

def create_session(conn, user_id: int, day: str, notes: Optional[str],
                   sets: List[Dict[str, Any]],
                   routine_day_id: Optional[int] = None) -> int:
    cur = conn.execute(
        "INSERT INTO workout_sessions (user_id, date, notes, routine_day_id) "
        "VALUES (?, ?, ?, ?)",
        (user_id, day, notes, routine_day_id),
    )
    session_id = cur.lastrowid

    for i, s in enumerate(sets, start=1):
        if s.get("exercise_id"):
            exercise_id = int(s["exercise_id"])
        else:
            ex = ensure_exercise(conn, user_id, s["exercise_name"],
                                 s.get("muscle_group"), s.get("equipment"),
                                 s.get("movement_pattern"))
            exercise_id = ex["id"]
        set_number = s.get("set_number")
        if set_number is None:
            set_number = i
        conn.execute(
            "INSERT INTO workout_sets "
            "(session_id, exercise_id, set_number, reps, weight, rpe) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, exercise_id, set_number, int(s["reps"]),
             float(s["weight"]),
             float(s["rpe"]) if s.get("rpe") not in (None, "") else None),
        )
    conn.commit()
    return session_id


def list_sessions(conn, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    sessions = conn.execute(
        "SELECT * FROM workout_sessions WHERE user_id=? "
        "ORDER BY date DESC, id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    if not sessions:
        return []
    ids = [row["id"] for row in sessions]
    placeholders = ",".join("?" for _ in ids)
    sets = conn.execute(
        f"""
        SELECT ws.*, e.name AS exercise_name, e.muscle_group
        FROM workout_sets ws
        JOIN exercises e ON e.id = ws.exercise_id
        WHERE ws.session_id IN ({placeholders})
        ORDER BY ws.set_number
        """,
        ids,
    ).fetchall()
    by_session: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for s in sets:
        by_session[s["session_id"]].append(dict(s))
    out = []
    for row in sessions:
        d = dict(row)
        d["sets"] = by_session.get(row["id"], [])
        out.append(d)
    return out


# ==========================================================================
# Daily check-ins
# ==========================================================================

def upsert_checkin(conn, user_id: int, day: str, sleep_hours=None, stress=None,
                   body_weight=None, nutrition=None, calories=None,
                   notes=None) -> None:
    conn.execute(
        """
        INSERT INTO daily_checkins
            (user_id, date, sleep_hours, stress, body_weight, nutrition, calories, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET
            sleep_hours=excluded.sleep_hours, stress=excluded.stress,
            body_weight=excluded.body_weight, nutrition=excluded.nutrition,
            calories=excluded.calories, notes=excluded.notes
        """,
        (user_id, day, sleep_hours, stress, body_weight, nutrition, calories, notes),
    )
    conn.commit()


def list_checkins(conn, user_id: int, limit: int = 60) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM daily_checkins WHERE user_id=? ORDER BY date DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


# ==========================================================================
# Split templates (reference)
# ==========================================================================

def list_templates(conn) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM split_templates ORDER BY num_days, name"
    ).fetchall()
    return [dict(r) for r in rows]


def get_template_full(conn, key: str) -> Optional[Dict[str, Any]]:
    tpl = conn.execute("SELECT * FROM split_templates WHERE key=?",
                       (key,)).fetchone()
    if not tpl:
        return None
    out = dict(tpl)
    days = conn.execute(
        "SELECT * FROM split_template_days WHERE template_id=? ORDER BY day_index",
        (tpl["id"],),
    ).fetchall()
    out["days"] = []
    for d in days:
        ex = conn.execute(
            """
            SELECT tde.*, e.id AS exercise_id, e.name, e.muscle_group,
                   e.movement_pattern, e.equipment
            FROM split_template_day_exercises tde
            JOIN exercises e ON e.slug = tde.exercise_slug
            WHERE tde.template_day_id=? ORDER BY tde.display_order
            """,
            (d["id"],),
        ).fetchall()
        dd = dict(d)
        dd["exercises"] = [dict(x) for x in ex]
        out["days"].append(dd)
    return out


# ==========================================================================
# Routines
# ==========================================================================

def get_active_routine(conn, user_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM routines WHERE user_id=? AND is_active=1 "
        "ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()


def day_with_exercises(conn, routine_day_id: int) -> Optional[Dict[str, Any]]:
    d = conn.execute("SELECT * FROM routine_days WHERE id=?",
                     (routine_day_id,)).fetchone()
    if not d:
        return None
    ex = conn.execute(
        """
        SELECT rde.*, e.name, e.muscle_group, e.movement_pattern, e.equipment
        FROM routine_day_exercises rde
        JOIN exercises e ON e.id = rde.exercise_id
        WHERE rde.routine_day_id=? ORDER BY rde.display_order
        """,
        (routine_day_id,),
    ).fetchall()
    out = dict(d)
    out["exercises"] = [dict(x) for x in ex]
    return out


def get_routine_full(conn, user_id: int) -> Optional[Dict[str, Any]]:
    routine = get_active_routine(conn, user_id)
    if not routine:
        return None
    out = dict(routine)
    days = conn.execute(
        "SELECT * FROM routine_days WHERE routine_id=? ORDER BY day_index",
        (routine["id"],),
    ).fetchall()
    out["days"] = [day_with_exercises(conn, d["id"]) for d in days]
    return out


def _write_routine_days(conn, user_id: int, routine_id: int,
                        days: List[Dict[str, Any]]) -> None:
    """Replace a routine's days + exercises with the supplied structure."""
    for od in conn.execute("SELECT id FROM routine_days WHERE routine_id=?",
                           (routine_id,)).fetchall():
        conn.execute("DELETE FROM routine_day_exercises WHERE routine_day_id=?",
                     (od["id"],))
    conn.execute("DELETE FROM routine_days WHERE routine_id=?", (routine_id,))

    for di, day in enumerate(days):
        cur = conn.execute(
            "INSERT INTO routine_days (user_id, routine_id, day_index, label) "
            "VALUES (?, ?, ?, ?)",
            (user_id, routine_id, di, day["label"]),
        )
        rd_id = cur.lastrowid
        for oi, ex in enumerate(day.get("exercises", [])):
            conn.execute(
                "INSERT INTO routine_day_exercises "
                "(user_id, routine_day_id, exercise_id, display_order, "
                " target_sets, target_rep_low, target_rep_high) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, rd_id, int(ex["exercise_id"]), oi,
                 ex.get("target_sets"), ex.get("target_rep_low"),
                 ex.get("target_rep_high")),
            )


def save_routine(conn, user_id: int, name: str, days: List[Dict[str, Any]],
                 source_template_key: Optional[str] = None,
                 changed_at: Optional[str] = None) -> int:
    """
    Save the user's active routine as a NEW version and record the change in
    routine_history (so the engine can read how long the plan has been unchanged).

    Editing creates a new routine row and deactivates the old one, rather than
    rewriting the existing days in place. This keeps referential integrity —
    past workout_sessions still point at the day rows they were logged against —
    and gives a real version history. `changed_at` overrides the timestamp (the
    seeder backdates the demo so it reads as unchanged for weeks).
    """
    existing = get_active_routine(conn, user_id)
    if existing:
        conn.execute("UPDATE routines SET is_active=0 WHERE id=?",
                     (existing["id"],))
        change_type = "edited"
        source_template_key = source_template_key or existing["source_template_key"]
    else:
        change_type = "created"

    cur = conn.execute(
        "INSERT INTO routines (user_id, name, source_template_key, is_active, "
        "created_at, updated_at) VALUES (?, ?, ?, 1, "
        "COALESCE(?, datetime('now')), COALESCE(?, datetime('now')))",
        (user_id, name, source_template_key, changed_at, changed_at))
    routine_id = cur.lastrowid  # brand-new row => _write_routine_days is FK-safe

    _write_routine_days(conn, user_id, routine_id, days)
    conn.execute(
        "INSERT INTO routine_history (user_id, routine_id, changed_at, "
        "change_type, snapshot_json) VALUES (?, ?, COALESCE(?, datetime('now')), ?, ?)",
        (user_id, routine_id, changed_at, change_type,
         json.dumps({"name": name, "days": days})),
    )
    conn.commit()
    return routine_id


def routine_from_template(conn, user_id: int, key: str) -> Optional[int]:
    """Instantiate the user's active routine from a built-in template."""
    tpl = get_template_full(conn, key)
    if not tpl:
        return None
    days = []
    for d in tpl["days"]:
        exs = [{
            "exercise_id": x["exercise_id"],
            "target_sets": x["target_sets"],
            "target_rep_low": x["target_rep_low"],
            "target_rep_high": x["target_rep_high"],
        } for x in d["exercises"]]
        days.append({"label": d["label"], "exercises": exs})
    return save_routine(conn, user_id, tpl["name"], days, source_template_key=key)


def routine_age_weeks(conn, routine_id: int) -> Optional[float]:
    """Weeks since the routine last changed (latest routine_history row)."""
    row = conn.execute(
        "SELECT MAX(changed_at) AS last FROM routine_history WHERE routine_id=?",
        (routine_id,),
    ).fetchone()
    if not row or not row["last"]:
        return None
    try:
        last = date.fromisoformat(row["last"][:10])
    except ValueError:
        return None
    return max(0.0, (date.today() - last).days / 7.0)


def suggest_next_day(conn, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Suggest the next routine day: the one after the most recently logged day in
    the routine's order (wrapping), or the first day if none logged yet.
    """
    routine = get_active_routine(conn, user_id)
    if not routine:
        return None
    days = conn.execute(
        "SELECT * FROM routine_days WHERE routine_id=? ORDER BY day_index",
        (routine["id"],),
    ).fetchall()
    if not days:
        return None
    last = conn.execute(
        "SELECT routine_day_id FROM workout_sessions "
        "WHERE user_id=? AND routine_day_id IS NOT NULL "
        "ORDER BY date DESC, id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    idx = 0
    if last and last["routine_day_id"] is not None:
        order = [d["id"] for d in days]
        if last["routine_day_id"] in order:
            idx = (order.index(last["routine_day_id"]) + 1) % len(days)
    return day_with_exercises(conn, days[idx]["id"])


# ==========================================================================
# Mapping DB rows -> engine input types
# ==========================================================================

def load_exercise_sessions(conn, user_id: int,
                           exercise_id: int) -> List[ExerciseSession]:
    rows = conn.execute(
        """
        SELECT wses.date AS day, ws.reps, ws.weight, ws.rpe
        FROM workout_sets ws
        JOIN workout_sessions wses ON wses.id = ws.session_id
        WHERE wses.user_id = ? AND ws.exercise_id = ?
        ORDER BY wses.date
        """,
        (user_id, exercise_id),
    ).fetchall()
    by_day: Dict[str, List[SetLog]] = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(SetLog(reps=r["reps"], weight=r["weight"],
                                       rpe=r["rpe"]))
    return [ExerciseSession(date=date.fromisoformat(day), sets=sets)
            for day, sets in sorted(by_day.items())]


def load_contexts(conn, user_id: int) -> List[DailyContext]:
    rows = conn.execute(
        "SELECT * FROM daily_checkins WHERE user_id=? ORDER BY date", (user_id,)
    ).fetchall()
    return [
        DailyContext(date=date.fromisoformat(r["date"]),
                     sleep_hours=r["sleep_hours"], stress=r["stress"],
                     body_weight=r["body_weight"], nutrition=r["nutrition"])
        for r in rows
    ]


def routine_context_for(conn, user_id: int,
                        exercise: sqlite3.Row) -> Optional[RoutineContext]:
    """
    Build the engine's RoutineContext for one exercise from the active routine:
    target sets/reps, declared weekly frequency (days that include it), routine
    age, and the count of distinct movement patterns trained for its muscle group.
    Returns None if the user has no active routine.
    """
    routine = get_active_routine(conn, user_id)
    if not routine:
        return None
    rid = routine["id"]

    planned = conn.execute(
        """
        SELECT rde.target_sets, rde.target_rep_low, rde.target_rep_high
        FROM routine_day_exercises rde
        JOIN routine_days rd ON rd.id = rde.routine_day_id
        WHERE rd.routine_id = ? AND rde.exercise_id = ?
        """,
        (rid, exercise["id"]),
    ).fetchall()

    declared_freq = float(len(planned)) if planned else None
    target_sets = rep_low = rep_high = None
    if planned:
        set_vals = [p["target_sets"] for p in planned if p["target_sets"] is not None]
        target_sets = max(set_vals) if set_vals else None
        rep_low = planned[0]["target_rep_low"]
        rep_high = planned[0]["target_rep_high"]

    patterns = conn.execute(
        """
        SELECT COUNT(DISTINCT e.movement_pattern) AS c
        FROM routine_day_exercises rde
        JOIN routine_days rd ON rd.id = rde.routine_day_id
        JOIN exercises e ON e.id = rde.exercise_id
        WHERE rd.routine_id = ? AND e.muscle_group = ?
        """,
        (rid, exercise["muscle_group"]),
    ).fetchone()
    pattern_count = patterns["c"] if patterns and patterns["c"] else None

    return RoutineContext(
        target_sets=target_sets,
        target_rep_low=rep_low,
        target_rep_high=rep_high,
        declared_freq_per_week=declared_freq,
        routine_age_weeks=routine_age_weeks(conn, rid),
        muscle_pattern_count=pattern_count,
    )


# ==========================================================================
# Persisting engine output
# ==========================================================================

def save_report(conn, user_id: int, exercise_id: int,
                report: Dict[str, Any]) -> None:
    conn.execute(
        "DELETE FROM plateau_reports WHERE user_id=? AND exercise_id=?",
        (user_id, exercise_id),
    )
    conn.execute(
        """
        INSERT INTO plateau_reports
            (user_id, exercise_id, generated_at, window_start, window_end,
             is_plateau, primary_metric, report_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, exercise_id, report.get("generated_at"),
         report.get("window_start"), report.get("window_end"),
         1 if report["plateau"]["is_plateau"] else 0,
         report["plateau"].get("metric"), json.dumps(report)),
    )
    conn.commit()
