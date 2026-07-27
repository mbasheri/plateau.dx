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

# --- Frequency-aware plateau window --------------------------------------
# We no longer use a fixed session count. A plateau means roughly this many
# WEEKS of no new estimated-1RM high; the window in SESSIONS is DERIVED from
# training frequency so its calendar meaning stays constant whether a lift is
# trained once or three times a week. See engine/detection.py:plateau_window().
#
# ASSUMPTION: ~3 weeks of no new high == a plateau worth diagnosing.
#   window_sessions = clamp(round(TARGET_PLATEAU_WEEKS * sessions_per_week),
#                           MIN_PLATEAU_WINDOW_SESSIONS, MAX_PLATEAU_WINDOW_SESSIONS)
# Worked: 1x/wk -> 3 sessions (~3wk); 2x/wk -> 6 (~3wk); 3x/wk -> 9 (~3wk).
TARGET_PLATEAU_WEEKS = 3.0

# Clamp on the derived window: never flag on too little evidence (floor), never
# demand an absurd count for very high-frequency lifts (cap).
MIN_PLATEAU_WINDOW_SESSIONS = 3
MAX_PLATEAU_WINDOW_SESSIONS = 10

# Cadence (sessions/week) assumed only when NEITHER the routine's planned
# frequency NOR the logged cadence is available (e.g. a brand-new off-plan lift
# with <3 logged sessions). Per review, the ROUTINE's declared frequency is the
# primary driver; the logged median-gap cadence is the fallback; this is the
# last resort.
DEFAULT_FREQUENCY_PER_WEEK = 2.0

# We need at least (window + 1) sessions to judge: one baseline plus a full
# stalled window. This floor protects the very-low-frequency case so a 1x/week
# lifter isn't forced to log many weeks before ANY verdict.
MIN_SESSIONS_FLOOR = MIN_PLATEAU_WINDOW_SESSIONS + 1  # = 4

# Noise floor for what counts as a genuine improvement. A session only sets a
# "new high" if its primary metric beats the previous best by MORE than this
# fraction. Default 0.015 (1.5%) absorbs plate-rounding and normal day-to-day
# variation, e.g. 100.0 -> 101.0 (+1.0%) is treated as flat, not progress.
# ASSUMPTION: <1.5% session-over-session == noise, not real progress.
IMPROVEMENT_NOISE_FRACTION = 0.015


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
# Used only when there is no routine target to compare against.
LOW_SETS_PER_SESSION = 3

# When a routine IS declared, insufficient stimulus becomes measurable: we fire
# if the sets actually performed fall short of the planned target by at least
# this many sets on average (e.g. plan 4, log <=3 => 1 set short).
# ASSUMPTION: averaging >=1 full set under the plan is a real volume shortfall.
SET_SHORTFALL_SETS = 1.0


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

# When a routine IS declared, staleness becomes direct: fire if the routine
# itself (the plan) has gone unchanged for at least this many weeks. Read from
# routine_history via RoutineContext.routine_age_weeks.
# ASSUMPTION: a plan left untouched for 6+ weeks is stale programming.
STALE_ROUTINE_WEEKS = 6.0


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
