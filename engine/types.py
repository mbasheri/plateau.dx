"""
types.py — the data shapes that flow through the engine.

Design goals:
  * The engine is a PURE module. It knows nothing about SQLite, FastAPI, HTTP
    or JSON. It takes the dataclasses defined here as input and returns the
    dataclasses defined here as output. The server maps DB rows -> these types
    on the way in, and these types -> JSON on the way out.
  * Everything the engine concludes is INSPECTABLE. A DiagnosisReport carries
    the exact metric series it saw, every Signal it evaluated (with the real
    number and the threshold it was compared against), and why each Cause fired.
    You should never have to guess why the engine said what it said.

INPUT types:  SetLog, ExerciseSession, DailyContext, ExerciseInfo
OUTPUT types: Signal, Cause, SessionMetric, PlateauResult, DiagnosisReport
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, List, Optional


# ===========================================================================
# INPUT TYPES  (server builds these from the database)
# ===========================================================================

@dataclass
class SetLog:
    """A single working set."""
    reps: int
    weight: float
    rpe: Optional[float] = None  # 1-10 perceived effort; optional by design


@dataclass
class ExerciseSession:
    """
    Every set of ONE exercise performed on ONE date. This is the atomic unit of
    plateau detection: we track how an exercise's best effort trends session to
    session.
    """
    date: date
    sets: List[SetLog] = field(default_factory=list)


@dataclass
class DailyContext:
    """
    Lifestyle inputs for a single date. Today these come from the user's daily
    check-in; later they can be sourced/overridden by wearables without changing
    this shape or the engine.
    """
    date: date
    sleep_hours: Optional[float] = None
    stress: Optional[int] = None          # 1 (calm) .. 5 (very stressed)
    body_weight: Optional[float] = None
    nutrition: Optional[str] = None       # 'under' | 'enough' | 'over'


@dataclass
class ExerciseInfo:
    """Identity of the exercise being diagnosed."""
    id: int
    name: str
    muscle_group: str
    modality: str = "barbell"


# ===========================================================================
# OUTPUT TYPES  (engine produces these; server serializes them)
# ===========================================================================

@dataclass
class SessionMetric:
    """
    The derived, comparable numbers for one exercise-session. This is exactly
    what plateau detection walks over, and it is included in the report so the
    UI can chart it and you can audit the verdict.
    """
    date: date
    top_weight: float             # heaviest weight touched that day
    est_1rm: float                # best Epley estimated 1RM across the sets
    volume: float                 # sum of weight*reps across all sets
    num_sets: int                 # count of working sets that day
    top_set_reps: int             # reps performed on the top set
    avg_rpe: Optional[float]      # mean RPE across sets (if logged)
    max_rpe: Optional[float]      # hardest set's RPE (if logged)
    is_new_high: bool             # did this session beat the running best?


@dataclass
class Signal:
    """
    One piece of evidence a rule evaluated. Whether it triggered or not, it is
    recorded so the reasoning is fully transparent — you can see what the engine
    looked at and how the real value compared to the threshold.
    """
    name: str                     # machine id, e.g. "avg_sleep"
    value: Any                    # the observed value
    threshold: Any                # what it was compared against
    direction: str                # below | above | rising | falling | flat | equal
    note: str                     # human-readable, includes the real numbers
    triggered: bool               # did this signal contribute to the cause?


@dataclass
class Cause:
    """
    A candidate explanation for the plateau, with its evidence and prescription.
    `score` is the summed weight of the signals that fired; `confidence` is the
    human label derived from it (see thresholds.py).
    """
    id: str                       # 'fatigue', 'insufficient_stimulus', ...
    label: str                    # display name
    confidence: str               # 'high' | 'medium' | 'low'
    score: float                  # summed weight of triggered signals
    signals: List[Signal]         # ALL signals considered (triggered or not)
    explanation: str              # why this cause, in plain language + numbers
    fix: str                      # the recommended action


@dataclass
class PlateauResult:
    """The output of plateau detection, before any cause reasoning."""
    is_plateau: bool
    enough_data: bool             # False => we decline to judge
    metric: str                   # which primary metric was used, e.g. "est_1rm"
    length_sessions: int          # sessions since the last new high
    length_weeks: float           # calendar weeks since the last new high
    series: List[SessionMetric]   # the full metric series the engine saw
    reason: str                   # plain-language detection explanation


@dataclass
class DiagnosisReport:
    """
    The complete, self-describing result for one exercise. Everything the UI and
    the persisted `plateau_reports.report_json` need lives here.
    """
    exercise: ExerciseInfo
    generated_at: str             # ISO timestamp
    window_start: Optional[date]
    window_end: Optional[date]
    sessions_analyzed: int
    plateau: PlateauResult
    causes: List[Cause]           # ranked best-first; empty if not a plateau
    summary: str                  # the headline paragraph
