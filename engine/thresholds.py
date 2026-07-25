"""
thresholds.py — ALL tunable knobs for the plateau-diagnosis engine.

This is deliberately the ONLY place magic numbers live. Every threshold the
detection and cause-reasoning logic depends on is defined here, with a comment
explaining what it means and why the default was chosen. The reasoning rules
will need to be tuned over time against real data, so keep them centralized.

Nothing in here is "settled science" — these are transparent, defensible
starting points. Adjust freely; the engine and its explanations update
automatically because every rule reads from this module.

Units note: the engine is UNIT-AGNOSTIC. It only ever compares a lift against
its own past (relative deltas), so lb vs kg does not matter here.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# PLATEAU DETECTION
# ---------------------------------------------------------------------------

# How many of the most-recent exercise-sessions must show NO new personal high
# before we call it a plateau. Set to 5 => "no progress for the last 5 sessions"
# (~2 weeks for someone training a lift 2-3x/week, so one bad session doesn't
# read as a stall).
# ASSUMPTION: 5 sessions with no new high == plateau. Raise for a stricter,
# slower-to-fire signal; lower to catch stalls sooner (more false positives).
# Tune this to YOUR frequency: ~3 suits ~1x/week per lift, ~5 suits 2-3x/week.
PLATEAU_WINDOW_SESSIONS = 5

# Minimum number of logged sessions for an exercise before we are willing to
# render *any* verdict. With fewer than this we say "not enough data" rather
# than guessing. Set to 6 => at least one baseline session plus the plateau window.
MIN_SESSIONS_TO_JUDGE = 6

# Noise floor for what counts as a genuine improvement. A session only sets a
# "new high" if its primary metric beats the previous best by MORE than this
# fraction. Default 0.015 (1.5%) absorbs plate-rounding and normal day-to-day
# variation, e.g. 100.0 -> 101.0 (+1.0%) is treated as flat, not progress.
# ASSUMPTION: <1.5% session-over-session == noise, not real progress.
IMPROVEMENT_NOISE_FRACTION = 0.015

# How many recent sessions the cause-engine looks across to compute trends
# (RPE creeping, sleep declining, etc.). Slightly wider than the plateau window
# so there is a baseline session to measure the trend against.
ANALYSIS_WINDOW_SESSIONS = PLATEAU_WINDOW_SESSIONS + 1  # = 6


# ---------------------------------------------------------------------------
# FATIGUE / OVERTRAINING signals
# ---------------------------------------------------------------------------

# Average nightly sleep (hours) at or below which recovery is likely impaired.
# ASSUMPTION: <6.5h average is a fatigue contributor for most lifters.
SLEEP_LOW_HOURS = 6.5

# Drop in average sleep across the window (hours) that counts as "declining".
SLEEP_DECLINE_HOURS = 0.75

# Average stress (on the 1-5 self-report scale) at or above which stress is a
# meaningful recovery drain. Default 3.5 => sits between "moderate" and "high".
STRESS_HIGH = 3.5

# Rise in average stress across the window that counts as "rising".
STRESS_RISE = 0.75

# Increase in RPE across the window, at flat load, that signals declining
# "RPE efficiency" — i.e. the same weight is costing more effort. Default 1.0
# point on the 1-10 RPE scale.
# ASSUMPTION: +1.0 RPE at unchanged weight == the lift is getting harder.
RPE_RISE = 1.0

# Sessions-per-week for a movement above which frequency itself becomes an
# overtraining contributor (in combination with poor recovery).
HIGH_FREQUENCY_PER_WEEK = 3.0


# ---------------------------------------------------------------------------
# INSUFFICIENT-STIMULUS signals
# ---------------------------------------------------------------------------

# Average RPE at or below which the lifter clearly has gas left in the tank —
# implying the plateau is under-stimulation, not fatigue. Default 7.0 => the
# top sets are stopping ~3 reps shy of failure.
# ASSUMPTION: avg RPE <=7 means there is room to push harder.
RPE_HEADROOM = 7.0

# Working sets per session for this exercise below which volume looks too low
# to drive progress. This is a ROUGH per-exercise proxy for weekly volume
# (true weekly-sets-per-muscle needs cross-exercise aggregation, added later).
LOW_SETS_PER_SESSION = 3


# ---------------------------------------------------------------------------
# NUTRITION signals
# ---------------------------------------------------------------------------

# Fraction of daily check-ins in the window self-reported as "under" (ate too
# little) at or above which under-eating is flagged. Default 0.40 => 40%+ of
# days under.
UNDEREAT_RATIO = 0.40

# Body-weight loss across the window (as a fraction of starting weight) that,
# during a STRENGTH plateau, points at nutrition. Default 0.01 (1%). Losing
# weight while trying to get stronger is a classic strength-stall cause.
BODYWEIGHT_LOSS_FRACTION = 0.01


# ---------------------------------------------------------------------------
# PROGRAMMING-STALENESS signals
# ---------------------------------------------------------------------------

# Number of consecutive sessions with NO variation in the rep scheme (same top-
# set reps every time) that counts as stale programming. The STALE_WEEKS guard
# below is usually the binding one; this mainly protects low-frequency lifters.
STALE_SESSIONS = 5

# ...and the same idea expressed in calendar time. Both the session count AND
# the time span should be met to flag staleness on a slow-frequency lifter.
STALE_WEEKS = 4.0


# ---------------------------------------------------------------------------
# TECHNIQUE / GRINDING signals
# ---------------------------------------------------------------------------

# RPE at or above which a set is a near-maximal grind. Repeatedly grinding the
# same weight (RPE >= 9, no weight increase) points at a technical sticking
# point rather than simple under-stimulation.
RPE_GRIND = 9.0


# ---------------------------------------------------------------------------
# CAUSE RANKING / CONFIDENCE
# ---------------------------------------------------------------------------

# A cause is only reported if its accumulated signal score exceeds this. Signal
# weights are defined per-rule in rules.py; this is the "is it worth mentioning"
# gate.
CAUSE_MIN_SCORE = 1.0

# Score thresholds that map a cause's accumulated signal weight onto a
# human-facing confidence label. Tune these alongside the per-signal weights.
CONFIDENCE_HIGH_SCORE = 3.0
CONFIDENCE_MEDIUM_SCORE = 2.0

# How many causes to surface as "likely cause(s)" in the headline summary.
MAX_HEADLINE_CAUSES = 2
