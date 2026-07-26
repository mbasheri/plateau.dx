"""
metrics.py — pure numeric helpers shared by detection and the cause rules.

Kept separate so the "what do we measure" decisions (how we estimate a 1RM, how
we collapse a session's many sets into one comparable number, how we measure a
trend) are in one place and easy to tweak or unit-test in isolation.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import List, Optional, Sequence

from .types import ExerciseSession, SessionMetric, SetLog


def epley_1rm(weight: float, reps: int) -> float:
    """
    Estimated one-rep max via the Epley formula: weight * (1 + reps/30).

    We use estimated 1RM as the PRIMARY progression metric because it captures
    weight AND reps in one number: adding a rep at the same weight, or adding
    weight at the same reps, both raise it. A single top-set weight would miss
    rep progress; raw volume would reward "junk" fatigue sets. Epley is a
    transparent, widely used approximation — swap it here if you prefer another.
    """
    if reps <= 0:
        return 0.0
    return weight * (1.0 + reps / 30.0)


def _mean(values: Sequence[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def summarize_session(session: ExerciseSession) -> SessionMetric:
    """
    Collapse one exercise-session's sets into the comparable numbers detection
    and the rules operate on. `is_new_high` is filled in later by detection,
    which needs the running best across sessions; here it defaults to False.
    """
    working: List[SetLog] = [s for s in session.sets if s.reps > 0]
    if not working:
        return SessionMetric(
            date=session.date, top_weight=0.0, est_1rm=0.0, volume=0.0,
            num_sets=0, top_set_reps=0, avg_rpe=None, max_rpe=None,
            is_new_high=False,
        )

    # Top set = the set with the greatest estimated 1RM (best single effort).
    top_set = max(working, key=lambda s: epley_1rm(s.weight, s.reps))
    est = epley_1rm(top_set.weight, top_set.reps)
    top_weight = max(s.weight for s in working)
    volume = sum(s.weight * s.reps for s in working)

    rpes = [s.rpe for s in working if s.rpe is not None]
    avg_rpe = _mean(rpes) if rpes else None
    max_rpe = max(rpes) if rpes else None

    return SessionMetric(
        date=session.date,
        top_weight=top_weight,
        est_1rm=est,
        volume=volume,
        num_sets=len(working),
        top_set_reps=top_set.reps,
        avg_rpe=avg_rpe,
        max_rpe=max_rpe,
        is_new_high=False,
    )


def linear_trend(values: Sequence[Optional[float]]) -> Optional[float]:
    """
    Simple first-vs-last delta across a window (last - first), ignoring None.
    Positive => rising, negative => falling. Returns None if <2 usable points.

    We intentionally use a plain endpoint delta rather than a least-squares
    slope: it is trivial to explain to the user ("sleep went from 7.2h to 5.4h")
    and robust enough for the short windows we analyze.
    """
    usable = [v for v in values if v is not None]
    if len(usable) < 2:
        return None
    return usable[-1] - usable[0]


def weeks_between(first: date, last: date) -> float:
    """Calendar weeks between two dates (>=0)."""
    return max(0.0, (last - first).days / 7.0)


def logged_frequency_per_week(dates: Sequence[date]) -> Optional[float]:
    """
    Sessions per week inferred from the MEDIAN gap between consecutive session
    dates. Median (not mean) so a single missed week doesn't distort the cadence.
    Returns None with fewer than 3 distinct dates (too little to infer a rhythm).
    """
    ds = sorted(set(dates))
    if len(ds) < 3:
        return None
    gaps = [(ds[i] - ds[i - 1]).days for i in range(1, len(ds))]
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return None
    med = statistics.median(gaps)
    if med <= 0:
        return None
    return 7.0 / med
