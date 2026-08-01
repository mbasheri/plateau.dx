"""
detection.py — is this exercise plateaued?

The single responsibility here is: given the sessions for one exercise, produce
a PlateauResult. No cause reasoning happens here — that's rules.py.

Frequency-aware window
----------------------
The plateau window is NOT a fixed session count. A plateau means roughly
TARGET_PLATEAU_WEEKS of no new estimated-1RM high; the window in SESSIONS is
derived from how often the lift is trained, so its calendar meaning is constant:

    window = clamp(round(TARGET_PLATEAU_WEEKS * sessions_per_week),
                   MIN_PLATEAU_WINDOW_SESSIONS, MAX_PLATEAU_WINDOW_SESSIONS)

Why: a fixed "5 sessions" is 5 weeks for a 1x/week lift on a 5-day split (far too
late) but under 2 weeks for a 3x/week full-body lift (too early). Sizing by
frequency keeps "a plateau" ≈ 3 weeks either way.

Cadence source (per review, routine is primary):
    1. the routine's DECLARED frequency for this lift (its intent), else
    2. the LOGGED cadence (median gap between actual sessions), else
    3. DEFAULT_FREQUENCY_PER_WEEK.
Both the session count and the calendar weeks are always reported so the number
stays interpretable.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional, Sequence, Tuple

from . import thresholds as T
from .metrics import logged_frequency_per_week, summarize_session, weeks_between
from .types import ExerciseSession, PlateauResult, RoutineContext, SessionMetric

PRIMARY_METRIC = "est_1rm"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def effective_frequency(
    dates: Sequence[date],
    routine: Optional[RoutineContext],
) -> Tuple[float, str]:
    """
    Return (sessions_per_week, source). The routine's declared cadence is the
    primary driver; the logged median-gap cadence is the fallback; a constant is
    the last resort. `source` is carried into the report for transparency.
    """
    if routine is not None and routine.declared_freq_per_week:
        return float(routine.declared_freq_per_week), "routine"
    logged = logged_frequency_per_week(dates)
    if logged is not None:
        return logged, "logged"
    return T.DEFAULT_FREQUENCY_PER_WEEK, "default"


def plateau_window(freq_per_week: float) -> int:
    """Derive the plateau window (in sessions) from training frequency."""
    raw = round(T.TARGET_PLATEAU_WEEKS * freq_per_week)
    return int(_clamp(raw, T.MIN_PLATEAU_WINDOW_SESSIONS,
                      T.MAX_PLATEAU_WINDOW_SESSIONS))


def _mark_new_highs(metrics: List[SessionMetric]) -> None:
    """
    Mutate `metrics` in place, setting is_new_high on each session.

    The first session with a positive metric establishes the baseline and counts
    as a high (there is nothing before it to beat). Thereafter a session must
    exceed the running best by more than the noise fraction to count.
    """
    best = 0.0
    established = False
    for m in metrics:
        value = getattr(m, PRIMARY_METRIC)
        if value <= 0:
            m.is_new_high = False
            continue
        if not established:
            m.is_new_high = True
            best = value
            established = True
            continue
        required = best * (1.0 + T.IMPROVEMENT_NOISE_FRACTION)
        if value > required:
            m.is_new_high = True
            best = value
        else:
            m.is_new_high = False


def _sessions_since_last_high(metrics: List[SessionMetric]) -> int:
    """How many sessions have occurred AFTER the most recent new high."""
    last_high_index = -1
    for i, m in enumerate(metrics):
        if m.is_new_high:
            last_high_index = i
    if last_high_index < 0:
        return 0
    return (len(metrics) - 1) - last_high_index


def detect_plateau(
    sessions: List[ExerciseSession],
    routine: Optional[RoutineContext] = None,
) -> PlateauResult:
    """Reduce sessions to a plateau verdict plus the evidence series."""
    ordered = sorted(sessions, key=lambda s: s.date)
    metrics: List[SessionMetric] = [summarize_session(s) for s in ordered]

    freq, source = effective_frequency([m.date for m in metrics], routine)
    window = plateau_window(freq)
    min_to_judge = max(T.MIN_SESSIONS_FLOOR, window + 1)

    # Not enough history to responsibly judge anything.
    if len(metrics) < min_to_judge:
        return PlateauResult(
            is_plateau=False,
            enough_data=False,
            metric=PRIMARY_METRIC,
            length_sessions=0,
            length_weeks=0.0,
            series=metrics,
            reason=(
                f"Only {len(metrics)} session(s) logged; need at least "
                f"{min_to_judge} to judge (window {window} at ~{freq:.1f}x/week)."
            ),
            window_sessions=window,
            frequency_per_week=round(freq, 2),
            frequency_source=source,
        )

    _mark_new_highs(metrics)
    since_high = _sessions_since_last_high(metrics)
    is_plateau = since_high >= window

    # Calendar length of the stall: from the last new high to the latest session.
    last_high_index = len(metrics) - 1 - since_high
    length_weeks = weeks_between(metrics[last_high_index].date, metrics[-1].date)

    if is_plateau:
        reason = (
            f"No new estimated-1RM high in the last {since_high} sessions "
            f"(~{length_weeks:.1f} weeks). At ~{freq:.1f}x/week the plateau "
            f"window is {window} sessions; best remains "
            f"{getattr(metrics[last_high_index], PRIMARY_METRIC):.1f}."
        )
    else:
        reason = (
            f"Still progressing — a new estimated-1RM high was set "
            f"{since_high} session(s) ago (window {window} at ~{freq:.1f}x/week)."
        )

    return PlateauResult(
        is_plateau=is_plateau,
        enough_data=True,
        metric=PRIMARY_METRIC,
        length_sessions=since_high,
        length_weeks=length_weeks,
        series=metrics,
        reason=reason,
        window_sessions=window,
        frequency_per_week=round(freq, 2),
        frequency_source=source,
    )
