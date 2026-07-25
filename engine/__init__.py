"""
Plateau-diagnosis engine — public API.

This package is a PURE module: no database, no web framework, no I/O. Feed it the
input dataclasses and it returns a DiagnosisReport. The server is responsible for
loading rows from SQLite, mapping them to these types, and serializing the result
(use `to_serializable` for JSON-safe output).

Typical use:

    from engine import diagnose_exercise, to_serializable
    report = diagnose_exercise(exercise_info, sessions, daily_contexts, goal)
    payload = to_serializable(report)     # -> plain dict, dates as ISO strings
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime

from .diagnose import diagnose_exercise
from .types import (
    Cause,
    DailyContext,
    DiagnosisReport,
    ExerciseInfo,
    ExerciseSession,
    PlateauResult,
    SessionMetric,
    SetLog,
    Signal,
)

__all__ = [
    "diagnose_exercise",
    "to_serializable",
    # input types
    "SetLog",
    "ExerciseSession",
    "DailyContext",
    "ExerciseInfo",
    # output types
    "DiagnosisReport",
    "PlateauResult",
    "SessionMetric",
    "Cause",
    "Signal",
]


def _jsonify(obj):
    """Recursively convert dates/datetimes to ISO strings for JSON output."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    return obj


def to_serializable(obj):
    """
    Turn any engine dataclass (e.g. a DiagnosisReport) into a plain,
    JSON-serializable structure with dates rendered as ISO-8601 strings.
    """
    if is_dataclass(obj):
        return _jsonify(asdict(obj))
    return _jsonify(obj)
