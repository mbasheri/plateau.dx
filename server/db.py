"""
db.py — SQLite connection + schema.

Deliberately thin and transparent: one file, plain SQL, no ORM. The database is
a single file (data/fitness.db) you can open with any SQLite browser to see
exactly what the app stored and what the engine read.

Schema overview
---------------
users            one row per user (MVP seeds a single user, id=1). weight_unit
                 and goal are per-user settings.
exercises        catalog of movements (name + muscle_group + modality), unique
                 per user. Logging can add new ones on the fly.
workout_sessions a training day (date + notes).
workout_sets     individual sets, each tied to a session and an exercise.
daily_checkins   lightweight daily lifestyle inputs (one row per user per date).
plateau_reports  persisted engine output; report_json holds the FULL diagnosis
                 so every past verdict stays fully inspectable.

Wearable-ready: device metrics would land in a future `device_daily_metrics`
table keyed by (date, source); the engine's data loader would prefer those and
fall back to daily_checkins — no change to the tables below.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# data/fitness.db, resolved relative to the project root (parent of server/).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = Path(os.environ.get("FITNESS_DB", DATA_DIR / "fitness.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT    NOT NULL,
    weight_unit  TEXT    NOT NULL DEFAULT 'lb',   -- display only; engine is unit-agnostic
    goal         TEXT    NOT NULL DEFAULT 'strength', -- strength | hypertrophy | general
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exercises (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    name         TEXT    NOT NULL,
    muscle_group TEXT    NOT NULL DEFAULT 'other',
    modality     TEXT    NOT NULL DEFAULT 'barbell',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS workout_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    date       TEXT    NOT NULL,                 -- ISO yyyy-mm-dd
    notes      TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workout_sets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    set_number  INTEGER NOT NULL,
    reps        INTEGER NOT NULL,
    weight      REAL    NOT NULL,
    rpe         REAL,                            -- nullable: RPE is optional
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_checkins (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    date        TEXT    NOT NULL,
    sleep_hours REAL,
    stress      INTEGER,                         -- 1..5
    body_weight REAL,
    nutrition   TEXT,                            -- under | enough | over
    calories    INTEGER,                         -- reserved for future use
    notes       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, date)
);

CREATE TABLE IF NOT EXISTS plateau_reports (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id),
    exercise_id    INTEGER NOT NULL REFERENCES exercises(id),
    generated_at   TEXT    NOT NULL,
    window_start   TEXT,
    window_end     TEXT,
    is_plateau     INTEGER NOT NULL,             -- 0/1
    primary_metric TEXT,
    report_json    TEXT    NOT NULL              -- full DiagnosisReport as JSON
);

CREATE INDEX IF NOT EXISTS idx_sets_exercise ON workout_sets(exercise_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON workout_sessions(user_id, date);
CREATE INDEX IF NOT EXISTS idx_checkins_user ON daily_checkins(user_id, date);
"""


def connect() -> sqlite3.Connection:
    """Open a connection with row access by name and FK enforcement on."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Create tables/indexes if they don't exist yet."""
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_db():
    """FastAPI dependency: yield a connection, always close it."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
