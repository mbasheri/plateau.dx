"""
db.py — SQLite connection, schema, and migrations.

Deliberately thin and transparent: one file, plain SQL, no ORM. The database is
a single file you can open with any SQLite browser to see exactly what the app
stored and what the engine read.

Schema overview
---------------
users                    one row per user (MVP seeds a single user, id=1).
exercises                the exercise LIBRARY. Built-in lifts are GLOBAL
                         (user_id IS NULL); user-added ones carry their user_id.
                         Tagged with muscle_group, movement_pattern, equipment,
                         is_compound — the engine reads movement_pattern.
workout_sessions         a training day (date + notes + optional routine_day_id).
workout_sets             individual sets, tied to a session and an exercise.
daily_checkins           lightweight daily lifestyle inputs (one per user/date).
plateau_reports          persisted engine output (full DiagnosisReport JSON).

split_templates          seeded reference splits (PPL, U/L, ...). user_id NULL =
split_template_days      built-in; nullable so a custom user template is possible.
split_template_day_exercises   default exercises per template day (by slug).

routines                 the user's ACTIVE routine (created/updated timestamps).
routine_days             named days within a routine.
routine_day_exercises    exercise + order + target sets/rep-range per day.
routine_history          one row per change, so the engine can read how long the
                         plan has gone unchanged.

Migration: init_db() upgrades an existing DB in place — it rebuilds the old
`exercises` table (per-user, `modality`) into the new global-catalog shape, and
adds workout_sessions.routine_day_id — then creates any missing new tables.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
# Env override kept as FITNESS_DB for continuity with existing local databases.
DB_PATH = Path(os.environ.get("FITNESS_DB", DATA_DIR / "fitness.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT    NOT NULL,
    weight_unit  TEXT    NOT NULL DEFAULT 'lb',
    goal         TEXT    NOT NULL DEFAULT 'strength',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Exercise LIBRARY. user_id IS NULL => global built-in; otherwise a user custom.
CREATE TABLE IF NOT EXISTS exercises (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER REFERENCES users(id),      -- NULL = global built-in
    slug             TEXT,                              -- stable id for built-ins
    name             TEXT    NOT NULL,
    muscle_group     TEXT    NOT NULL DEFAULT 'other',
    movement_pattern TEXT    NOT NULL DEFAULT 'other',
    equipment        TEXT    NOT NULL DEFAULT 'barbell',
    is_compound      INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS workout_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    date          TEXT    NOT NULL,
    notes         TEXT,
    routine_day_id INTEGER REFERENCES routine_days(id),  -- which planned day, if any
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workout_sets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    set_number  INTEGER NOT NULL,
    reps        INTEGER NOT NULL,
    weight      REAL    NOT NULL,
    rpe         REAL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_checkins (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    date        TEXT    NOT NULL,
    sleep_hours REAL,
    stress      INTEGER,
    body_weight REAL,
    nutrition   TEXT,
    calories    INTEGER,
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
    is_plateau     INTEGER NOT NULL,
    primary_metric TEXT,
    report_json    TEXT    NOT NULL
);

-- ---- Split templates (seeded reference; user_id NULL = built-in) ----------
CREATE TABLE IF NOT EXISTS split_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id),
    key         TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    description TEXT,
    num_days    INTEGER NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS split_template_days (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES split_templates(id) ON DELETE CASCADE,
    day_index   INTEGER NOT NULL,
    label       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS split_template_day_exercises (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    template_day_id INTEGER NOT NULL REFERENCES split_template_days(id) ON DELETE CASCADE,
    exercise_slug   TEXT    NOT NULL,
    display_order   INTEGER NOT NULL DEFAULT 0,
    target_sets     INTEGER,
    target_rep_low  INTEGER,
    target_rep_high INTEGER
);

-- ---- The user's active routine -------------------------------------------
CREATE TABLE IF NOT EXISTS routines (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    name                TEXT    NOT NULL,
    source_template_key TEXT,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS routine_days (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
    day_index  INTEGER NOT NULL,
    label      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS routine_day_exercises (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    routine_day_id  INTEGER NOT NULL REFERENCES routine_days(id) ON DELETE CASCADE,
    exercise_id     INTEGER NOT NULL REFERENCES exercises(id),
    display_order   INTEGER NOT NULL DEFAULT 0,
    target_sets     INTEGER,
    target_rep_low  INTEGER,
    target_rep_high INTEGER
);

CREATE TABLE IF NOT EXISTS routine_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    routine_id  INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
    changed_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    change_type TEXT    NOT NULL,           -- 'created' | 'edited'
    snapshot_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_sets_exercise ON workout_sets(exercise_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON workout_sessions(user_id, date);
CREATE INDEX IF NOT EXISTS idx_checkins_user ON daily_checkins(user_id, date);
CREATE INDEX IF NOT EXISTS idx_exercises_lookup ON exercises(user_id, name);
CREATE INDEX IF NOT EXISTS idx_routine_days ON routine_days(routine_id, day_index);
"""


def connect() -> sqlite3.Connection:
    """Open a connection with row access by name and FK enforcement on."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _columns(conn: sqlite3.Connection, table: str):
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


def _rebuild_exercises_if_old(conn: sqlite3.Connection) -> None:
    """
    Upgrade a pre-splits `exercises` table (per-user NOT NULL user_id, `modality`,
    no tags) to the new global-catalog shape. SQLite can't ALTER a column to drop
    NOT NULL, so we rebuild the table, preserving ids (workout_sets FKs stay
    valid). Skipped on a fresh DB (no table) or one already migrated.
    """
    cols = _columns(conn, "exercises")
    if not cols or "movement_pattern" in cols:
        return  # fresh DB (created by SCHEMA later) or already migrated

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        CREATE TABLE exercises_new (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER REFERENCES users(id),
            slug             TEXT,
            name             TEXT    NOT NULL,
            muscle_group     TEXT    NOT NULL DEFAULT 'other',
            movement_pattern TEXT    NOT NULL DEFAULT 'other',
            equipment        TEXT    NOT NULL DEFAULT 'barbell',
            is_compound      INTEGER NOT NULL DEFAULT 1,
            created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, name)
        );
        INSERT INTO exercises_new
            (id, user_id, slug, name, muscle_group, movement_pattern,
             equipment, is_compound, created_at)
        SELECT id, user_id, NULL, name, muscle_group, 'other',
               COALESCE(modality, 'barbell'), 1, created_at
        FROM exercises;
        DROP TABLE exercises;
        ALTER TABLE exercises_new RENAME TO exercises;
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def _add_column_if_missing(conn, table, column, decl) -> None:
    if table in [r["name"] for r in
                 conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
        if column not in _columns(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            conn.commit()


def init_db() -> None:
    """Create/upgrade the schema. Safe on both a fresh and an existing DB."""
    conn = connect()
    try:
        _rebuild_exercises_if_old(conn)          # old per-user table -> global
        conn.executescript(SCHEMA)               # create anything missing
        _add_column_if_missing(conn, "workout_sessions", "routine_day_id",
                               "INTEGER REFERENCES routine_days(id)")
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
