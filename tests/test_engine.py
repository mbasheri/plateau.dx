"""
End-to-end tests for the CAUSE engine: given a plateau, does it reach the right
explanation for the right reason? Each test constructs a scenario where one
cause should clearly dominate, and asserts it comes out on top. These are the
tests to lean on when tuning the rules.

Note: several scenarios use days=3 spacing (~2x/week) so the calendar span stays
under the 4-week staleness guard, isolating the cause under test.
"""

import json

from engine import diagnose_exercise, to_serializable
from tests.helpers import BENCH, contexts, sessions


def test_fatigue_is_top_cause_when_recovery_craters():
    # Flat weight, RPE creeping up, sleep falling, stress rising = under-recovery.
    s = sessions([
        (100, 5, 7.0), (100, 5, 7.0), (100, 5, 7.5), (100, 5, 8.0),
        (100, 5, 8.5), (100, 5, 9.0), (100, 5, 9.0), (100, 5, 9.5),
    ])
    c = contexts([
        {"sleep": 7.0, "stress": 2}, {"sleep": 6.8, "stress": 2},
        {"sleep": 6.6, "stress": 3}, {"sleep": 6.2, "stress": 3},
        {"sleep": 5.8, "stress": 4}, {"sleep": 5.4, "stress": 4},
        {"sleep": 5.0, "stress": 5}, {"sleep": 4.8, "stress": 5},
    ])
    r = diagnose_exercise(BENCH, s, c, goal="strength")

    assert r.plateau.is_plateau is True
    assert r.causes[0].id == "fatigue"
    assert r.causes[0].confidence == "high"
    assert "plateaued" in r.summary.lower()
    # The explanation must cite real evidence, not just a verdict.
    assert any(sig.triggered for sig in r.causes[0].signals)


def test_insufficient_stimulus_when_effort_is_low():
    # Flat weight but easy sets (RPE 6) and no attempt to progress. Weekly
    # cadence -> window 3. (No routine here, so this uses the log-only path.)
    s = sessions([(100, 5, 6.0)] * 6)
    c = contexts([{"sleep": 8, "stress": 2, "nutrition": "enough"}] * 6)
    r = diagnose_exercise(BENCH, s, c, goal="strength")

    assert r.causes[0].id == "insufficient_stimulus"
    assert r.causes[0].confidence == "high"


def test_nutrition_when_undereating_and_losing_weight():
    s = sessions([(100, 5, 7.5)] * 6)
    c = contexts([
        {"sleep": 7.5, "stress": 2, "bw": 80.0, "nutrition": "under"},
        {"sleep": 7.5, "stress": 2, "bw": 79.6, "nutrition": "under"},
        {"sleep": 7.5, "stress": 2, "bw": 79.2, "nutrition": "under"},
        {"sleep": 7.5, "stress": 2, "bw": 78.8, "nutrition": "under"},
        {"sleep": 7.5, "stress": 2, "bw": 78.4, "nutrition": "under"},
        {"sleep": 7.5, "stress": 2, "bw": 78.0, "nutrition": "under"},
    ])
    r = diagnose_exercise(BENCH, s, c, goal="strength")

    assert r.causes[0].id == "nutrition"


def test_staleness_when_nothing_changes_for_weeks():
    # Seven identical weekly sessions (>4 weeks), recovery fine, effort moderate.
    s = sessions([(100, 5, 7.5)] * 7)
    c = contexts([{"sleep": 8, "stress": 2, "nutrition": "enough"}] * 7)
    r = diagnose_exercise(BENCH, s, c, goal="strength")

    assert r.causes[0].id == "programming_staleness"


def test_technique_when_grinding_at_high_rpe():
    # Flat weight, RPE spiking to a grind, but recovery is fine and the span is
    # short (so it's a technique issue, not staleness). days=3 => ~2.3x/week =>
    # window 7, so 8 sessions clears min-to-judge while spanning <4 weeks.
    s = sessions([
        (100, 5, 8.0), (100, 5, 8.0), (100, 5, 8.5), (100, 5, 9.0),
        (100, 5, 9.0), (100, 5, 9.0), (100, 5, 9.5), (100, 5, 9.5),
    ], days=3)
    c = contexts([{"sleep": 8, "stress": 2}] * 8, days=3)
    r = diagnose_exercise(BENCH, s, c, goal="strength")

    assert r.causes[0].id == "technique"


def test_progressing_lift_has_no_causes():
    s = sessions([
        (100, 5, 7), (102.5, 5, 7), (105, 5, 7),
        (107.5, 5, 7), (110, 5, 7), (112.5, 5, 7), (115, 5, 7),
    ])
    c = contexts([{"sleep": 8, "stress": 2}] * 7)
    r = diagnose_exercise(BENCH, s, c)

    assert r.plateau.is_plateau is False
    assert r.causes == []
    assert "progressing" in r.summary.lower()


def test_report_is_json_serializable():
    s = sessions([(100, 5, 9)] * 8)
    c = contexts([{"sleep": 5, "stress": 5}] * 8)
    r = diagnose_exercise(BENCH, s, c)

    payload = to_serializable(r)
    json.dumps(payload)  # must not raise
    assert payload["exercise"]["name"] == "Bench Press"
    assert payload["plateau"]["is_plateau"] is True
    # Dates must have been rendered as ISO strings.
    assert isinstance(payload["window_start"], str)