"""
Tests for the routine-driven engine upgrades (Part A):
  * the frequency-aware plateau window,
  * routine cadence as the primary window driver,
  * low-frequency lifts flagged neither prematurely nor too late,
  * measurable insufficient stimulus (planned vs. performed sets),
  * direct programming staleness (routine age + movement-pattern rotation).
"""

from datetime import date, timedelta

from engine import RoutineContext, diagnose_exercise
from engine.detection import detect_plateau, effective_frequency, plateau_window
from tests.helpers import BENCH, contexts, sessions


# --------------------------------------------------------------------------
# Frequency-aware window sizing
# --------------------------------------------------------------------------

def test_window_scales_with_frequency():
    # ~3 weeks of no progress, expressed in sessions at each cadence.
    assert plateau_window(1.0) == 3   # 1x/week -> 3 sessions
    assert plateau_window(2.0) == 6   # 2x/week -> 6 sessions
    assert plateau_window(3.0) == 9   # 3x/week -> 9 sessions


def test_window_is_clamped():
    assert plateau_window(0.2) == 3    # floor (MIN_PLATEAU_WINDOW_SESSIONS)
    assert plateau_window(9.0) == 10   # cap  (MAX_PLATEAU_WINDOW_SESSIONS)


def test_routine_cadence_is_primary():
    # Logged cadence is weekly, but the routine declares 3x/week -> routine wins.
    dates = [date(2026, 1, 5) + timedelta(days=7 * i) for i in range(4)]
    freq, src = effective_frequency(dates, RoutineContext(declared_freq_per_week=3.0))
    assert src == "routine" and freq == 3.0

    # No routine -> fall back to the logged median-gap cadence.
    freq2, src2 = effective_frequency(dates, None)
    assert src2 == "logged" and round(freq2, 1) == 1.0

    # Nothing measurable -> the default.
    freq3, src3 = effective_frequency(dates[:1], None)
    assert src3 == "default"


# --------------------------------------------------------------------------
# Low-frequency splits: not premature, not delayed
# --------------------------------------------------------------------------

def test_low_frequency_flags_at_three_sessions_not_five():
    # 1x/week lift stalled for 3 sessions -> plateau at ~3 weeks (the old fixed
    # window of 5 would have made a 1x/week lifter wait ~5 weeks).
    s = sessions([(100, 5, 7), (102.5, 5, 7), (105, 5, 7),
                  (105, 5, 7), (105, 5, 7), (105, 5, 7)])
    r = detect_plateau(s)
    assert r.frequency_source == "logged"
    assert r.window_sessions == 3
    assert r.is_plateau is True
    assert r.length_sessions == 3


def test_low_frequency_two_stalled_sessions_is_not_premature():
    # Same 1x/week lift, only 2 sessions since the last high -> not yet a plateau.
    s = sessions([(100, 5, 7), (102.5, 5, 7), (105, 5, 7),
                  (105, 5, 7), (105, 5, 7)])
    r = detect_plateau(s)
    assert r.window_sessions == 3
    assert r.is_plateau is False


def test_high_frequency_needs_more_sessions_before_flagging():
    # Routine says 3x/week -> window 9, so a 6-session stall must NOT flag yet
    # (would be premature at <2 weeks under the old fixed window).
    s = sessions([(100, 5, 7)] * 6, days=2)
    r = detect_plateau(s, RoutineContext(declared_freq_per_week=3.0))
    assert r.window_sessions == 9
    assert r.frequency_source == "routine"
    assert r.is_plateau is False


# --------------------------------------------------------------------------
# Measurable insufficient stimulus
# --------------------------------------------------------------------------

def test_below_target_sets_makes_insufficient_measurable():
    # Routine plans 4 sets; the athlete logs 2. Direct, evidenced shortfall.
    s = sessions([(100, 5, 8.0)] * 6, n_sets=2)
    c = contexts([{"sleep": 8, "stress": 2}] * 6)
    routine = RoutineContext(target_sets=4)
    r = diagnose_exercise(BENCH, s, c, goal="strength", routine=routine)

    top = r.causes[0]
    assert top.id == "insufficient_stimulus"
    assert any(sig.name == "below_target_sets" and sig.triggered
               for sig in top.signals)


# --------------------------------------------------------------------------
# Direct programming staleness
# --------------------------------------------------------------------------

def test_staleness_is_direct_from_routine():
    # Plan unchanged 8 weeks and a single movement pattern for the muscle group.
    s = sessions([(100, 5, 7.5)] * 6)
    c = contexts([{"sleep": 8, "stress": 2}] * 6)
    routine = RoutineContext(routine_age_weeks=8.0, muscle_pattern_count=1)
    r = diagnose_exercise(BENCH, s, c, goal="strength", routine=routine)

    top = r.causes[0]
    assert top.id == "programming_staleness"
    fired = {sig.name for sig in top.signals if sig.triggered}
    assert "routine_unchanged" in fired
    assert "no_pattern_rotation" in fired
    # The direct path is used, not the log-inference heuristic.
    assert not any(sig.name == "no_rep_variation" for sig in top.signals)
