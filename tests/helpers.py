"""
Test builders — concise constructors so each test reads as a scenario, not as
dataclass plumbing. One "week" = 7 days, sessions start on a fixed Monday.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List

from engine.types import DailyContext, ExerciseInfo, ExerciseSession, SetLog

MONDAY = date(2026, 1, 5)

BENCH = ExerciseInfo(id=1, name="Bench Press", muscle_group="chest",
                     modality="barbell")


def _date_for_index(i: int, days: int) -> date:
    return MONDAY + timedelta(days=days * i)


def sessions(specs, days: int = 7) -> List[ExerciseSession]:
    """
    Build a series of sessions. `specs` is a list of (weight, reps, rpe) tuples,
    one per session. `days` is the spacing between sessions (default 7 = weekly;
    use 3 to simulate ~2x/week, which keeps the calendar span short).
    """
    out = []
    for i, (weight, reps, rpe) in enumerate(specs):
        out.append(ExerciseSession(
            date=_date_for_index(i, days),
            sets=[SetLog(reps=reps, weight=weight, rpe=rpe) for _ in range(3)],
        ))
    return out


def contexts(specs, days: int = 7) -> List[DailyContext]:
    """
    Build daily check-ins aligned to the session dates (same `days` spacing).
    Each spec is a dict with optional keys: sleep, stress, bw, nutrition.
    """
    out = []
    for i, s in enumerate(specs):
        out.append(DailyContext(
            date=_date_for_index(i, days),
            sleep_hours=s.get("sleep"),
            stress=s.get("stress"),
            body_weight=s.get("bw"),
            nutrition=s.get("nutrition"),
        ))
    return out
