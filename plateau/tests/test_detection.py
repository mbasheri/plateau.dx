"""
Tests for plateau DETECTION only (is the lift stalled?), independent of cause
reasoning. These pin down the thresholds in thresholds.py — if you change a
threshold and a test fails, that's the test doing its job; update it
deliberately. (Current defaults: plateau window 5, need >=6 sessions to judge.)
"""

from engine.detection import detect_plateau
from tests.helpers import sessions


def test_not_enough_data_declines_to_judge():
    # 3 weekly sessions -> ~1x/week -> window 3, so min-to-judge is 4.
    r = detect_plateau(sessions([(100, 5, 7)] * 3))
    assert r.enough_data is False
    assert r.is_plateau is False


def test_flat_series_is_a_plateau():
    # 8 identical sessions: only the first is a "high", the rest are flat.
    r = detect_plateau(sessions([(100, 5, 7)] * 8))
    assert r.enough_data is True
    assert r.is_plateau is True
    assert r.length_sessions == 7


def test_steady_progress_is_not_a_plateau():
    r = detect_plateau(sessions([
        (100, 5, 7), (102.5, 5, 7), (105, 5, 7),
        (107.5, 5, 7), (110, 5, 7), (112.5, 5, 7), (115, 5, 7),
    ]))
    assert r.is_plateau is False
    assert r.length_sessions == 0


def test_sub_noise_wobble_is_not_progress():
    # Every wobble is under the 1.5% noise floor -> still a plateau.
    r = detect_plateau(sessions([
        (100, 5, 7), (100.5, 5, 7), (99.5, 5, 7),
        (100.8, 5, 7), (100.2, 5, 7), (99.8, 5, 7), (100.6, 5, 7),
    ]))
    assert r.is_plateau is True


def test_a_recent_new_high_breaks_the_plateau():
    # Flat for a while, then a clear PR on the most recent session.
    r = detect_plateau(sessions([(100, 5, 7)] * 6 + [(110, 5, 7)]))
    assert r.is_plateau is False
    assert r.length_sessions == 0


def test_added_reps_at_same_weight_count_as_progress():
    # Same weight but climbing reps raises estimated 1RM -> not a plateau.
    r = detect_plateau(sessions([
        (100, 5, 8), (100, 6, 8), (100, 7, 8),
        (100, 8, 8), (100, 9, 8), (100, 10, 8),
    ]))
    assert r.is_plateau is False