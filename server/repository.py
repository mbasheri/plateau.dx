"""
repository.py — all SQL lives here, plus the mapping from DB rows to the engine's
input dataclasses.

This is the ONLY layer that knows both SQLite and the engine. Route handlers call
these functions; the engine never sees a database row. Keeping the boundary here
is what lets the engine stay pure and independently testable.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional

from engine.types import DailyContext, ExerciseInfo, ExerciseSession, SetLog


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------

def get_user(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def update_user(conn: sqlite3.Connection, user_id: int,
                display_name: str, weight_unit: str, goal: str) -> None:
    conn.execute(
        "UPDATE users SET display_name=?, weight_unit=?, goal=? WHERE id=?",
        (display_name, weight_unit, goal, user_id),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Exercises
# --------------------------------------------------------------------------

def list_exercises(conn: sqlite3.Connection, user_id: int) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM exercises WHERE user_id=? ORDER BY name", (user_id,)
    ).fetchall()


def ensure_exercise(conn: sqlite3.Connection, user_id: int, name: str,
                    muscle_group: Optional[str] = None,
                    modality: Optional[str] = None) -> sqlite3.Row:
    """
    Return the exercise with this name, creating it if needed (so logging can add
    movements on the fly). If it exists, optionally fill in muscle_group/modality
    when they were previously unset.
    """
    name = name.strip()
    row = conn.execute(
        "SELECT * FROM exercises WHERE user_id=? AND name=? COLLATE NOCASE",
        (user_id, name),
    ).fetchone()
    if row:
        return row
    conn.execute(
        "INSERT INTO exercises (user_id, name, muscle_group, modality) "
        "VALUES (?, ?, ?, ?)",
        (user_id, name, muscle_group or "other", modality or "barbell"),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM exercises WHERE user_id=? AND name=? COLLATE NOCASE",
        (user_id, name),
    ).fetchone()


def exercises_with_sessions(conn: sqlite3.Connection,
                            user_id: int) -> List[sqlite3.Row]:
    """Exercises that have at least one logged set (candidates for diagnosis)."""
    return conn.execute(
        """
        SELECT DISTINCT e.*
        FROM exercises e
        JOIN workout_sets s   ON s.exercise_id = e.id
        WHERE e.user_id = ?
        ORDER BY e.name
        """,
        (user_id,),
    ).fetchall()


# --------------------------------------------------------------------------
# Workout sessions + sets
# --------------------------------------------------------------------------

def create_session(conn: sqlite3.Connection, user_id: int, day: str,
                   notes: Optional[str], sets: List[Dict[str, Any]]) -> int:
    """
    Create a training session and its sets in one transaction. Each set dict may
    identify its exercise by `exercise_id` or by `exercise_name` (upserted).
    """
    cur = conn.execute(
        "INSERT INTO workout_sessions (user_id, date, notes) VALUES (?, ?, ?)",
        (user_id, day, notes),
    )
    session_id = cur.lastrowid

    for i, s in enumerate(sets, start=1):
        if s.get("exercise_id"):
            exercise_id = int(s["exercise_id"])
        else:
            ex = ensure_exercise(conn, user_id, s["exercise_name"],
                                 s.get("muscle_group"), s.get("modality"))
            exercise_id = ex["id"]
        # set_number may be present-but-None (pydantic dumps the key), so fall
        # back to the row index rather than relying on dict.get's default.
        set_number = s.get("set_number")
        if set_number is None:
            set_number = i
        conn.execute(
            "INSERT INTO workout_sets "
            "(session_id, exercise_id, set_number, reps, weight, rpe) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, exercise_id, set_number,
             int(s["reps"]), float(s["weight"]),
             float(s["rpe"]) if s.get("rpe") not in (None, "") else None),
        )
    conn.commit()
    return session_id


def list_sessions(conn: sqlite3.Connection, user_id: int,
                  limit: int = 50) -> List[Dict[str, Any]]:
    """Recent sessions with their sets nested (newest first), for the log view."""
    sessions = conn.execute(
        "SELECT * FROM workout_sessions WHERE user_id=? ORDER BY date DESC, id DESC "
        "LIMIT ?",
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


# --------------------------------------------------------------------------
# Daily check-ins
# --------------------------------------------------------------------------

def upsert_checkin(conn: sqlite3.Connection, user_id: int, day: str,
                   sleep_hours=None, stress=None, body_weight=None,
                   nutrition=None, calories=None, notes=None) -> None:
    """One check-in per user per date; re-submitting a date overwrites it."""
    conn.execute(
        """
        INSERT INTO daily_checkins
            (user_id, date, sleep_hours, stress, body_weight, nutrition, calories, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET
            sleep_hours=excluded.sleep_hours,
            stress=excluded.stress,
            body_weight=excluded.body_weight,
            nutrition=excluded.nutrition,
            calories=excluded.calories,
            notes=excluded.notes
        """,
        (user_id, day, sleep_hours, stress, body_weight, nutrition, calories, notes),
    )
    conn.commit()


def list_checkins(conn: sqlite3.Connection, user_id: int,
                  limit: int = 60) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM daily_checkins WHERE user_id=? ORDER BY date DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Mapping DB rows -> engine input types
# --------------------------------------------------------------------------

def load_exercise_sessions(conn: sqlite3.Connection, user_id: int,
                           exercise_id: int) -> List[ExerciseSession]:
    """
    All logged sets for one exercise, grouped into ExerciseSessions by date. This
    is exactly what the engine's detection walks over.
    """
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
        by_day[r["day"]].append(
            SetLog(reps=r["reps"], weight=r["weight"], rpe=r["rpe"])
        )

    return [
        ExerciseSession(date=date.fromisoformat(day), sets=sets)
        for day, sets in sorted(by_day.items())
    ]


def load_contexts(conn: sqlite3.Connection,
                  user_id: int) -> List[DailyContext]:
    """All daily check-ins mapped to the engine's DailyContext type."""
    rows = conn.execute(
        "SELECT * FROM daily_checkins WHERE user_id=? ORDER BY date", (user_id,)
    ).fetchall()
    return [
        DailyContext(
            date=date.fromisoformat(r["date"]),
            sleep_hours=r["sleep_hours"],
            stress=r["stress"],
            body_weight=r["body_weight"],
            nutrition=r["nutrition"],
        )
        for r in rows
    ]


def exercise_info(row: sqlite3.Row) -> ExerciseInfo:
    return ExerciseInfo(id=row["id"], name=row["name"],
                        muscle_group=row["muscle_group"], modality=row["modality"])


# --------------------------------------------------------------------------
# Persisting engine output
# --------------------------------------------------------------------------

def save_report(conn: sqlite3.Connection, user_id: int, exercise_id: int,
                report: Dict[str, Any]) -> None:
    """
    Persist a serialized DiagnosisReport, replacing any previous one for this
    exercise so the table always reflects the CURRENT verdict per exercise
    (keeps it clean and inspectable rather than growing on every dashboard load).
    """
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
        (
            user_id, exercise_id,
            report.get("generated_at"),
            report.get("window_start"),
            report.get("window_end"),
            1 if report["plateau"]["is_plateau"] else 0,
            report["plateau"].get("metric"),
            json.dumps(report),
        ),
    )
    conn.commit()
