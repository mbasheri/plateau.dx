"""
diagnose.py — the engine's public entry point.

Ties the two halves together for one exercise:
    detect_plateau(...)  ->  is it stalled?
    ALL_RULES(...)       ->  if so, why? (ranked, explained)

and packages the result as a DiagnosisReport. This is the ONE function the
server calls. It stays deliberately thin — detection and the rules hold the
real logic — so the flow of reasoning is easy to follow end to end.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from . import thresholds as T
from .detection import detect_plateau
from .rules import ALL_RULES, build_window
from .types import (
    Cause,
    DailyContext,
    DiagnosisReport,
    ExerciseInfo,
    ExerciseSession,
    PlateauResult,
)


def _confidence_for(score: float) -> str:
    """Map an accumulated signal score onto a human-facing confidence label."""
    if score >= T.CONFIDENCE_HIGH_SCORE:
        return "high"
    if score >= T.CONFIDENCE_MEDIUM_SCORE:
        return "medium"
    return "low"


def _rank_causes(
    metrics, contexts: List[DailyContext], goal: str
) -> List[Cause]:
    """Run every rule, keep the ones that meaningfully fired, rank best-first."""
    window = build_window(metrics, contexts, goal)

    scored: List[Cause] = []
    for rule in ALL_RULES:
        cause = rule(window)
        cause.confidence = _confidence_for(cause.score)
        if cause.score >= T.CAUSE_MIN_SCORE:
            scored.append(cause)

    # Highest score first; ties broken by number of signals that fired so the
    # better-evidenced cause wins.
    scored.sort(
        key=lambda c: (c.score, sum(1 for s in c.signals if s.triggered)),
        reverse=True,
    )
    return scored


def _summarize(
    exercise: ExerciseInfo, plateau: PlateauResult, causes: List[Cause]
) -> str:
    """Compose the headline paragraph shown at the top of a report."""
    if not plateau.enough_data:
        return (f"Not enough data yet to judge {exercise.name}. "
                f"{plateau.reason}")
    if not plateau.is_plateau:
        return (f"{exercise.name} is progressing — no plateau detected. "
                f"{plateau.reason}")

    weeks = plateau.length_weeks
    duration = (f"{weeks:.0f} weeks" if weeks >= 1
                else f"{plateau.length_sessions} sessions")
    head = (f"You've plateaued on {exercise.name} for {duration} "
            f"({plateau.length_sessions} sessions with no new high).")

    if not causes:
        return (head + " No single cause stands out from the data logged — the "
                "most likely levers are progressive overload and programming "
                "variation. Log sleep, stress and RPE to sharpen this.")

    top = causes[:T.MAX_HEADLINE_CAUSES]
    labels = " and ".join(f"{c.label.lower()} ({c.confidence} confidence)"
                          for c in top)
    lead = top[0]
    return (f"{head} Likely cause: {labels}. {lead.explanation} "
            f"Suggested fix: {lead.fix}")


def diagnose_exercise(
    exercise: ExerciseInfo,
    sessions: List[ExerciseSession],
    contexts: List[DailyContext],
    goal: str = "strength",
) -> DiagnosisReport:
    """
    Full diagnosis for one exercise.

    exercise : identity + muscle group.
    sessions : every logged session for this exercise (any order).
    contexts : the user's daily check-ins (the engine matches them by date).
    goal     : 'strength' | 'hypertrophy' | 'general' — tunes nutrition weighting.
    """
    plateau = detect_plateau(sessions)

    # Only reason about causes when there is a real, confirmed plateau.
    causes: List[Cause] = []
    if plateau.enough_data and plateau.is_plateau:
        causes = _rank_causes(plateau.series, contexts, goal)

    window_start = plateau.series[0].date if plateau.series else None
    window_end = plateau.series[-1].date if plateau.series else None

    return DiagnosisReport(
        exercise=exercise,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        window_start=window_start,
        window_end=window_end,
        sessions_analyzed=len(plateau.series),
        plateau=plateau,
        causes=causes,
        summary=_summarize(exercise, plateau, causes),
    )
