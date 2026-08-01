"""
db.py — Postgres connection + schema.

Migrated from SQLite to Postgres for the unified Vercel deployment. Two design
choices keep the rest of the data layer (repository.py, seed.py) almost
unchanged:

  * The `Conn` connection subclass rewrites SQLite-style "?" placeholders to
    psycopg's "%s" on the fly, so the existing SQL strings work as-is.
  * `row_factory=dict_row` returns plain dicts, which support both `row["col"]`
    and `dict(row)` exactly like the old `sqlite3.Row`.

Serverless model: each request opens its own connection and closes it (no
persistent pool). Seeding no longer runs on startup — it's a one-off script
(`python -m server.seed`) run against the database. See init_db()/DEPLOY.md.

Connection string comes from DATABASE_URL (or POSTGRES_URL, which Vercel's Neon
integration sets). Use the POOLED connection string on serverless.
"""

from __future__ import annotations

import os

import psycopg
from psycopg.rows import dict_row


def _dsn() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL (or POSTGRES_URL) is not set — point it at your "
            "Postgres connection string (use the pooled URL on serverless)."
        )
    return url


class Conn(psycopg.Connection):
    """
    psycopg connection that accepts the repository's SQLite-style "?" placeholders
    (rewriting them to "%s") so the existing SQL runs unchanged on Postgres. None
    of our SQL contains a literal "?" or "%", so the substitution is safe.
    """

    def execute(self, query, params=None, **kwargs):
        if isinstance(query, str) and "?" in query:
            query = query.replace("?", "%s")
        return super().execute(query, params, **kwargs)


def connect() -> psycopg.Connection:
    """Open a connection returning dict rows. Caller commits/closes."""
    return Conn.connect(_dsn(), row_factory=dict_row)


def get_db():
    """FastAPI dependency: yield a per-request connection, always close it."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema. Ordered so every REFERENCES target is created before it's used
# (Postgres, unlike SQLite, checks foreign-key targets at CREATE time).
# Dates/timestamps are stored as TEXT ISO strings, matching what the app inserts
# and what repository.py parses (date.fromisoformat / changed_at[:10]).
# ---------------------------------------------------------------------------

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id           SERIAL PRIMARY KEY,
        display_name TEXT    NOT NULL,
        weight_unit  TEXT    NOT NULL DEFAULT 'lb',
        goal         TEXT    NOT NULL DEFAULT 'strength',
        created_at   TEXT    NOT NULL DEFAULT (now()::text)
    )
    """,
    # Exercise LIBRARY. user_id IS NULL => global built-in; otherwise a user custom.
    """
    CREATE TABLE IF NOT EXISTS exercises (
        id               SERIAL PRIMARY KEY,
        user_id          INTEGER REFERENCES users(id),
        slug             TEXT,
        name             TEXT    NOT NULL,
        muscle_group     TEXT    NOT NULL DEFAULT 'other',
        movement_pattern TEXT    NOT NULL DEFAULT 'other',
        equipment        TEXT    NOT NULL DEFAULT 'barbell',
        is_compound      INTEGER NOT NULL DEFAULT 1,
        created_at       TEXT    NOT NULL DEFAULT (now()::text),
        UNIQUE(user_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS routines (
        id                  SERIAL PRIMARY KEY,
        user_id             INTEGER NOT NULL REFERENCES users(id),
        name                TEXT    NOT NULL,
        source_template_key TEXT,
        is_active           INTEGER NOT NULL DEFAULT 1,
        created_at          TEXT    NOT NULL DEFAULT (now()::text),
        updated_at          TEXT    NOT NULL DEFAULT (now()::text)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS routine_days (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
        day_index  INTEGER NOT NULL,
        label      TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workout_sessions (
        id             SERIAL PRIMARY KEY,
        user_id        INTEGER NOT NULL REFERENCES users(id),
        date           TEXT    NOT NULL,
        notes          TEXT,
        routine_day_id INTEGER REFERENCES routine_days(id),
        created_at     TEXT    NOT NULL DEFAULT (now()::text)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workout_sets (
        id          SERIAL PRIMARY KEY,
        session_id  INTEGER NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
        exercise_id INTEGER NOT NULL REFERENCES exercises(id),
        set_number  INTEGER NOT NULL,
        reps        INTEGER NOT NULL,
        weight      DOUBLE PRECISION NOT NULL,
        rpe         DOUBLE PRECISION,
        created_at  TEXT    NOT NULL DEFAULT (now()::text)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_checkins (
        id          SERIAL PRIMARY KEY,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        date        TEXT    NOT NULL,
        sleep_hours DOUBLE PRECISION,
        stress      INTEGER,
        body_weight DOUBLE PRECISION,
        nutrition   TEXT,
        calories    INTEGER,
        notes       TEXT,
        created_at  TEXT    NOT NULL DEFAULT (now()::text),
        UNIQUE(user_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plateau_reports (
        id             SERIAL PRIMARY KEY,
        user_id        INTEGER NOT NULL REFERENCES users(id),
        exercise_id    INTEGER NOT NULL REFERENCES exercises(id),
        generated_at   TEXT    NOT NULL,
        window_start   TEXT,
        window_end     TEXT,
        is_plateau     INTEGER NOT NULL,
        primary_metric TEXT,
        report_json    TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS split_templates (
        id          SERIAL PRIMARY KEY,
        user_id     INTEGER REFERENCES users(id),
        key         TEXT    NOT NULL,
        name        TEXT    NOT NULL,
        description TEXT,
        num_days    INTEGER NOT NULL,
        created_at  TEXT    NOT NULL DEFAULT (now()::text)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS split_template_days (
        id          SERIAL PRIMARY KEY,
        template_id INTEGER NOT NULL REFERENCES split_templates(id) ON DELETE CASCADE,
        day_index   INTEGER NOT NULL,
        label       TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS split_template_day_exercises (
        id              SERIAL PRIMARY KEY,
        template_day_id INTEGER NOT NULL REFERENCES split_template_days(id) ON DELETE CASCADE,
        exercise_slug   TEXT    NOT NULL,
        display_order   INTEGER NOT NULL DEFAULT 0,
        target_sets     INTEGER,
        target_rep_low  INTEGER,
        target_rep_high INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS routine_day_exercises (
        id              SERIAL PRIMARY KEY,
        user_id         INTEGER NOT NULL REFERENCES users(id),
        routine_day_id  INTEGER NOT NULL REFERENCES routine_days(id) ON DELETE CASCADE,
        exercise_id     INTEGER NOT NULL REFERENCES exercises(id),
        display_order   INTEGER NOT NULL DEFAULT 0,
        target_sets     INTEGER,
        target_rep_low  INTEGER,
        target_rep_high INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS routine_history (
        id            SERIAL PRIMARY KEY,
        user_id       INTEGER NOT NULL REFERENCES users(id),
        routine_id    INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
        changed_at    TEXT    NOT NULL DEFAULT (now()::text),
        change_type   TEXT    NOT NULL,
        snapshot_json TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sets_exercise ON workout_sets(exercise_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user ON workout_sessions(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_checkins_user ON daily_checkins(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_exercises_lookup ON exercises(user_id, name)",
    "CREATE INDEX IF NOT EXISTS idx_routine_days ON routine_days(routine_id, day_index)",
]


def init_db() -> None:
    """Create the schema if missing. Idempotent; safe to run repeatedly."""
    conn = connect()
    try:
        for stmt in SCHEMA:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()
