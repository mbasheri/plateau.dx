"""
detection.py — is this exercise plateaued?

The single responsibility here is: given the sessions for one exercise, produce
a PlateauResult. No cause reasoning happens here — that's rules.py. Keeping
detection separate means you can trust/tune "are they stalled?" independently of
"why are they stalled?".

Algorithm (all thresholds from thresholds.py):
  1. Sort sessions oldest -> newest and reduce each to a SessionMetric.
  2. Walk the estimated-1RM series tracking the running best. A session is a
     "new high" only if it beats the previous best by MORE than the noise floor
     (IMPROVEMENT_NOISE_FRACTION) — this is how we "account for normal week-to-
     week noise" rather than treating a 0.5% wobble as progress.
  3. Count how many sessions have passed since the last new high.
  4. It's a plateau if we have enough data AND that count >= the plateau window
     (i.e. the most recent N sessions produced no genuine new high).
"""

from __future__ import annotations

from typing import List

from . import thresholds as T
from .metrics import summarize_session, weeks_between
from .types import ExerciseSession, PlateauResult, SessionMetric

PRIMARY_METRIC = "est_1rm"


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


def detect_plateau(sessions: List[ExerciseSession]) -> PlateauResult:
    """Reduce sessions to a plateau verdict plus the evidence series."""
    ordered = sorted(sessions, key=lambda s: s.date)
    metrics: List[SessionMetric] = [summarize_session(s) for s in ordered]

    # Not enough history to responsibly judge anything.
    if len(metrics) < T.MIN_SESSIONS_TO_JUDGE:
        return PlateauResult(
            is_plateau=False,
            enough_data=False,
            metric=PRIMARY_METRIC,
            length_sessions=0,
            length_weeks=0.0,
            series=metrics,
            reason=(
                f"Only {len(metrics)} session(s) logged; need at least "
                f"{T.MIN_SESSIONS_TO_JUDGE} to judge a trend."
            ),
        )

    _mark_new_highs(metrics)
    since_high = _sessions_since_last_high(metrics)
    is_plateau = since_high >= T.PLATEAU_WINDOW_SESSIONS

    # Calendar length of the stall: from the last new high to the latest session.
    last_high_index = len(metrics) - 1 - since_high
    length_weeks = weeks_between(metrics[last_high_index].date, metrics[-1].date)

    if is_plateau:
        reason = (
            f"No new estimated-1RM high in the last {since_high} sessions "
            f"(~{length_weeks:.1f} weeks). Best remains "
            f"{getattr(metrics[last_high_index], PRIMARY_METRIC):.1f}."
        )
    else:
        reason = (
            f"Still progressing — a new estimated-1RM high was set "
            f"{since_high} session(s) ago."
        )

    return PlateauResult(
        is_plateau=is_plateau,
        enough_data=True,
        metric=PRIMARY_METRIC,
        length_sessions=since_high,
        length_weeks=length_weeks,
        series=metrics,
        reason=reason,
    )
