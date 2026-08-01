"""
rules.py — the root-cause reasoning engine (the core differentiator).

Given that an exercise IS plateaued (decided by detection.py), this module works
out the LIKELY CAUSE(S) and explains them in plain language backed by real
numbers. It is deliberately a transparent if/then rules engine, not an ML model:
every conclusion is traceable to named signals and the thresholds they crossed.

Shape of the logic
------------------
1. `build_window(...)` computes, ONCE, all the shared aggregates the rules need
   over the recent analysis window (sleep/stress/RPE trends, whether load was
   flat, whether overload was even attempted, nutrition, body-weight, frequency,
   rep-scheme staleness). Everything a rule reasons about is a field on the
   resulting WindowStats, so the inputs are inspectable in one place.

2. Each `rule_*` function evaluates its signals and returns a Cause. A Signal is
   recorded whether or not it fired, so you can see exactly what was considered.
   A Cause's `score` is the sum of the WEIGHTS of the signals that fired.

3. diagnose.py collects the causes, drops those below CAUSE_MIN_SCORE, ranks the
   rest by score, and maps score -> confidence label.

TUNING: signal thresholds live in thresholds.py. Signal WEIGHTS live here, next
to each rule, because a weight only means something relative to its sibling
signals. Both are meant to be adjusted as the rules meet real data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from . import thresholds as T
from .metrics import linear_trend, weeks_between
from .types import (
    Cause,
    DailyContext,
    RoutineContext,
    SessionMetric,
    Signal,
)


# ---------------------------------------------------------------------------
# Shared, precomputed view of the recent window
# ---------------------------------------------------------------------------

@dataclass
class WindowStats:
    """Everything the rules read, computed once. All fields are inspectable."""
    goal: str
    # session-derived
    window_metrics: List[SessionMetric]
    sessions_in_window: int
    weeks_spanned: float
    frequency_per_week: float
    load_flat: bool                     # top weight did not meaningfully rise
    overload_attempted: bool            # weight OR reps were pushed up at all
    avg_sets_per_session: float
    rpe_delta: Optional[float]          # avg-RPE last minus first (window)
    max_rpe: Optional[float]            # hardest set in the window
    avg_rpe: Optional[float]            # mean of session avg-RPEs
    # staleness: the trailing run of sessions using the SAME rep scheme as the
    # most recent session (this is what "unchanged for N weeks" really means).
    stale_reps: int                     # the rep scheme of that run
    stale_run_sessions: int             # how many sessions long the run is
    stale_run_weeks: float              # calendar span of the run
    stale_same_load: bool               # the run also used one identical load
    # lifestyle-derived
    avg_sleep: Optional[float]
    sleep_delta: Optional[float]
    avg_stress: Optional[float]
    stress_delta: Optional[float]
    undereat_ratio: Optional[float]
    bodyweight_delta_frac: Optional[float]
    context_days: int                   # how many daily check-ins we matched
    # routine-derived (all None when the user has no active routine, in which
    # case the rules fall back to log-only heuristics)
    target_sets: Optional[int] = None
    routine_age_weeks: Optional[float] = None
    muscle_pattern_count: Optional[int] = None


def _sig(name, value, threshold, direction, note, triggered) -> Signal:
    return Signal(name=name, value=value, threshold=threshold,
                  direction=direction, note=note, triggered=triggered)


def build_window(
    metrics: List[SessionMetric],
    contexts: List[DailyContext],
    goal: str,
    routine: Optional[RoutineContext] = None,
    analysis_window_sessions: Optional[int] = None,
) -> WindowStats:
    """
    Reduce the full session series + all daily contexts into the aggregates the
    rules need. `metrics` is the FULL, date-ordered series with is_new_high
    already marked by detection.

    `analysis_window_sessions` is the frequency-aware plateau window + 1 (passed
    by diagnose so trends are measured across the actual stalled period plus a
    baseline). `routine` carries the user's plan when they have one.
    """
    # --- the trend/analysis window: the most recent N sessions ---
    n_window = analysis_window_sessions or (T.MIN_PLATEAU_WINDOW_SESSIONS + 1)
    window = metrics[-n_window:]
    first, last = window[0], window[-1]
    weeks_spanned = weeks_between(first.date, last.date)

    # Sessions per week. If the window spans <1 week we still want a sane number,
    # so divide by at least a tiny epsilon and let the >=3/wk threshold catch it.
    freq = len(window) / weeks_spanned if weeks_spanned > 0 else float(len(window))

    # Load flat? Did top weight fail to rise beyond the noise floor across window?
    max_top = max(m.top_weight for m in window)
    load_flat = max_top <= first.top_weight * (1.0 + T.IMPROVEMENT_NOISE_FRACTION)

    # Overload attempted? Weight pushed up, OR reps pushed up at >= same weight.
    overload_attempted = False
    for m in window[1:]:
        if m.top_weight > first.top_weight * (1.0 + T.IMPROVEMENT_NOISE_FRACTION):
            overload_attempted = True
            break
        if (m.top_weight >= first.top_weight * (1.0 - T.IMPROVEMENT_NOISE_FRACTION)
                and m.top_set_reps > first.top_set_reps):
            overload_attempted = True
            break

    avg_sets = sum(m.num_sets for m in window) / len(window)

    # RPE trend across the window uses each session's average RPE.
    rpe_delta = linear_trend([m.avg_rpe for m in window])
    max_rpe_vals = [m.max_rpe for m in window if m.max_rpe is not None]
    max_rpe = max(max_rpe_vals) if max_rpe_vals else None
    avg_rpe_vals = [m.avg_rpe for m in window if m.avg_rpe is not None]
    avg_rpe = sum(avg_rpe_vals) / len(avg_rpe_vals) if avg_rpe_vals else None

    # --- staleness: walk backward from the most recent session while the rep
    # scheme is unchanged, to measure how long the lifter has repeated the exact
    # same set/rep prescription. This trailing-run measure is what actually
    # answers "same thing for N weeks?", independent of training frequency.
    stale_reps = metrics[-1].top_set_reps
    run = [metrics[-1]]
    for m in reversed(metrics[:-1]):
        if m.top_set_reps == stale_reps:
            run.append(m)
        else:
            break
    run.reverse()
    stale_run_sessions = len(run)
    stale_run_weeks = weeks_between(run[0].date, run[-1].date)
    stale_same_load = len({round(m.top_weight, 2) for m in run}) <= 1

    # --- lifestyle window: daily contexts within the analysis window's dates ---
    lo, hi = first.date, last.date
    win_ctx = sorted(
        [c for c in contexts if lo <= c.date <= hi], key=lambda c: c.date
    )

    def _avg(attr):
        vals = [getattr(c, attr) for c in win_ctx if getattr(c, attr) is not None]
        return sum(vals) / len(vals) if vals else None

    avg_sleep = _avg("sleep_hours")
    sleep_delta = linear_trend([c.sleep_hours for c in win_ctx])
    avg_stress = _avg("stress")
    stress_delta = linear_trend(
        [float(c.stress) if c.stress is not None else None for c in win_ctx]
    )

    nutri = [c.nutrition for c in win_ctx if c.nutrition is not None]
    undereat_ratio = (
        sum(1 for n in nutri if n == "under") / len(nutri) if nutri else None
    )

    bw = [c.body_weight for c in win_ctx if c.body_weight is not None]
    bodyweight_delta_frac = (
        (bw[-1] - bw[0]) / bw[0] if len(bw) >= 2 and bw[0] else None
    )

    return WindowStats(
        goal=goal,
        window_metrics=window,
        sessions_in_window=len(window),
        weeks_spanned=weeks_spanned,
        frequency_per_week=freq,
        load_flat=load_flat,
        overload_attempted=overload_attempted,
        avg_sets_per_session=avg_sets,
        rpe_delta=rpe_delta,
        max_rpe=max_rpe,
        avg_rpe=avg_rpe,
        stale_reps=stale_reps,
        stale_run_sessions=stale_run_sessions,
        stale_run_weeks=stale_run_weeks,
        stale_same_load=stale_same_load,
        avg_sleep=avg_sleep,
        sleep_delta=sleep_delta,
        avg_stress=avg_stress,
        stress_delta=stress_delta,
        undereat_ratio=undereat_ratio,
        bodyweight_delta_frac=bodyweight_delta_frac,
        context_days=len(win_ctx),
        target_sets=routine.target_sets if routine else None,
        routine_age_weeks=routine.routine_age_weeks if routine else None,
        muscle_pattern_count=routine.muscle_pattern_count if routine else None,
    )


def _weighted(cause_id, label, fix, weighted_signals) -> Cause:
    """
    weighted_signals: list of (Signal, weight). Score = sum of weights whose
    Signal.triggered is True. Explanation = the fired signals' notes joined.
    """
    signals = [s for s, _w in weighted_signals]
    score = sum(w for s, w in weighted_signals if s.triggered)
    fired_notes = [s.note for s in signals if s.triggered]
    explanation = " ".join(fired_notes) if fired_notes else ""
    return Cause(
        id=cause_id,
        label=label,
        confidence="",          # filled in by diagnose.py from the score
        score=round(score, 3),
        signals=signals,
        explanation=explanation,
        fix=fix,
    )


# ---------------------------------------------------------------------------
# RULE 1 — INSUFFICIENT STIMULUS
# "You're not giving the muscle a reason to adapt."
# Fires when overload was never attempted and/or effort is low and/or volume is
# low. This is the most common benign cause of an early plateau.
# ---------------------------------------------------------------------------

def rule_insufficient_stimulus(w: WindowStats) -> Cause:
    signals: list = []

    # Signal: RPE headroom — effort is low, there's clearly gas left in the tank
    # (weight 2.0 — this is the PRIMARY discriminator of under-stimulation vs.
    # every other cause: if the sets are easy, the stall isn't fatigue/technique/
    # nutrition, it's simply not enough of a demand).
    if w.avg_rpe is not None:
        triggered = w.avg_rpe <= T.RPE_HEADROOM
        note = (f"Average RPE is only {w.avg_rpe:.1f} (≤{T.RPE_HEADROOM}), "
                f"so the sets are stopping well short of failure — there's room "
                f"to push harder.")
    else:
        triggered = False
        note = "No RPE logged, so effort level is unknown."
    signals.append((_sig(
        name="rpe_headroom", value=w.avg_rpe, threshold=T.RPE_HEADROOM,
        direction="below", note=note, triggered=triggered,
    ), 2.0))

    # Signal: planned vs. performed sets — DIRECT, measurable evidence (weight
    # 2.0). Only when the user has a declared routine: if they plan N sets and
    # log fewer, that is a fact, not an inference from volume trends.
    if w.target_sets:
        shortfall = w.target_sets - w.avg_sets_per_session
        triggered = shortfall >= T.SET_SHORTFALL_SETS
        note = (f"Logged {w.avg_sets_per_session:.1f} of {w.target_sets} planned "
                f"sets ({shortfall:.1f} short) — the planned volume isn't being "
                f"delivered.") if triggered else ""
    else:
        triggered, note = False, ""
    signals.append((_sig(
        name="below_target_sets", value=round(w.avg_sets_per_session, 1),
        threshold=w.target_sets, direction="below", note=note, triggered=triggered,
    ), 2.0))

    # Signal: no progressive overload was even attempted (weight 1.0 — secondary,
    # because weight is trivially "flat" in any plateau; on its own it says little
    # unless effort is also low. It matters most when the lifter genuinely never
    # tried to add load or reps).
    triggered = not w.overload_attempted
    signals.append((_sig(
        name="no_overload_attempted",
        value=w.overload_attempted,
        threshold=True,
        direction="equal",
        note=("No progressive overload was attempted — the same weight and reps "
              "have been repeated, so there's no new stimulus to adapt to."),
        triggered=triggered,
    ), 1.0))

    # Signal: low working-set volume (rough proxy, weight 1.0). Only used when
    # there is NO routine target to compare against — the direct check above
    # supersedes it when a plan exists.
    triggered = (w.target_sets is None
                 and w.avg_sets_per_session < T.LOW_SETS_PER_SESSION)
    signals.append((_sig(
        name="low_volume",
        value=round(w.avg_sets_per_session, 1),
        threshold=T.LOW_SETS_PER_SESSION,
        direction="below",
        note=(f"Only {w.avg_sets_per_session:.1f} working sets per session "
              f"(<{T.LOW_SETS_PER_SESSION}) — volume may be too low to drive "
              f"progress."),
        triggered=triggered,
    ), 1.0))

    return _weighted(
        cause_id="insufficient_stimulus",
        label="Insufficient stimulus",
        fix=("Apply progressive overload deliberately: use double progression — "
             "add a rep each session until you hit the top of your rep range, "
             "then add the smallest load increment and start over. Consider "
             "adding a set or two if volume is low."),
        weighted_signals=signals,
    )


# ---------------------------------------------------------------------------
# RULE 2 — FATIGUE / OVERTRAINING
# "You're pushing, but not recovering enough to adapt."
# The signature is: effort rising (RPE creeping at flat load) while recovery
# inputs (sleep, stress, frequency) are poor. The more of these co-occur, the
# higher the confidence.
# ---------------------------------------------------------------------------

def rule_fatigue(w: WindowStats) -> Cause:
    signals: list = []

    # Signal: low average sleep (weight 1.5).
    if w.avg_sleep is not None:
        triggered = w.avg_sleep <= T.SLEEP_LOW_HOURS
        note = (f"Sleep has averaged {w.avg_sleep:.1f}h "
                f"(≤{T.SLEEP_LOW_HOURS}h), which impairs recovery.")
    else:
        triggered, note = False, "No sleep data logged."
    signals.append((_sig("avg_sleep", w.avg_sleep, T.SLEEP_LOW_HOURS,
                         "below", note, triggered), 1.5))

    # Signal: sleep trending down across the window (weight 1.0).
    if w.sleep_delta is not None:
        triggered = w.sleep_delta <= -T.SLEEP_DECLINE_HOURS
        note = (f"Sleep is declining (down {abs(w.sleep_delta):.1f}h across the "
                f"window).") if triggered else ""
    else:
        triggered, note = False, ""
    signals.append((_sig("sleep_trend", w.sleep_delta, -T.SLEEP_DECLINE_HOURS,
                         "falling", note, triggered), 1.0))

    # Signal: high average stress (weight 1.0).
    if w.avg_stress is not None:
        triggered = w.avg_stress >= T.STRESS_HIGH
        note = (f"Stress is high (averaging {w.avg_stress:.1f}/5), adding to the "
                f"recovery burden.") if triggered else ""
    else:
        triggered, note = False, ""
    signals.append((_sig("avg_stress", w.avg_stress, T.STRESS_HIGH,
                         "above", note, triggered), 1.0))

    # Signal: stress trending up (weight 0.75).
    if w.stress_delta is not None:
        triggered = w.stress_delta >= T.STRESS_RISE
        note = "Stress has been rising over the window." if triggered else ""
    else:
        triggered, note = False, ""
    signals.append((_sig("stress_trend", w.stress_delta, T.STRESS_RISE,
                         "rising", note, triggered), 0.75))

    # Signal: RPE creeping up at flat load — the same weight is costing more
    # effort, the classic under-recovery fingerprint (weight 1.5).
    if w.rpe_delta is not None and w.load_flat:
        triggered = w.rpe_delta >= T.RPE_RISE
        note = (f"RPE has climbed +{w.rpe_delta:.1f} while the weight stayed "
                f"flat — the lift is getting harder, not the load.") if triggered else ""
    else:
        triggered, note = False, ""
    signals.append((_sig("rpe_efficiency", w.rpe_delta, T.RPE_RISE,
                         "rising", note, triggered), 1.5))

    # Signal: high training frequency compounds poor recovery (weight 0.75).
    triggered = w.frequency_per_week >= T.HIGH_FREQUENCY_PER_WEEK
    note = (f"Training this movement ~{w.frequency_per_week:.1f}x/week leaves "
            f"little recovery time.") if triggered else ""
    signals.append((_sig("frequency", round(w.frequency_per_week, 2),
                         T.HIGH_FREQUENCY_PER_WEEK, "above", note, triggered),
                    0.75))

    return _weighted(
        cause_id="fatigue",
        label="Fatigue / under-recovery",
        fix=("Deload: drop working weight ~10% (or cut volume in half) for one "
             "week, and prioritise sleep and stress management. Rebuild load "
             "only once RPE at a given weight comes back down."),
        weighted_signals=signals,
    )


# ---------------------------------------------------------------------------
# RULE 3 — NUTRITION
# "You can't build what you don't fuel."
# Under-eating, and especially losing body weight during a STRENGTH plateau,
# points at nutrition. Weight loss is much less concerning for a general-fitness
# or fat-loss goal, so we weight it by goal.
# ---------------------------------------------------------------------------

def rule_nutrition(w: WindowStats) -> Cause:
    signals: list = []

    # Signal: frequently self-reporting under-eating (weight 1.5).
    if w.undereat_ratio is not None:
        triggered = w.undereat_ratio >= T.UNDEREAT_RATIO
        note = (f"You reported under-eating on {w.undereat_ratio*100:.0f}% of "
                f"logged days (≥{T.UNDEREAT_RATIO*100:.0f}%).") if triggered else ""
    else:
        triggered, note = False, ""
    signals.append((_sig("undereating", w.undereat_ratio, T.UNDEREAT_RATIO,
                         "above", note, triggered), 1.5))

    # Signal: losing body weight while trying to get stronger (weight 1.5, and
    # only counts for strength/hypertrophy goals).
    strength_goal = w.goal in ("strength", "hypertrophy")
    if w.bodyweight_delta_frac is not None and strength_goal:
        triggered = w.bodyweight_delta_frac <= -T.BODYWEIGHT_LOSS_FRACTION
        note = (f"Body weight fell {abs(w.bodyweight_delta_frac)*100:.1f}% during "
                f"the plateau — hard to gain strength in a deficit.") if triggered else ""
    else:
        triggered, note = False, ""
    signals.append((_sig("bodyweight_loss", w.bodyweight_delta_frac,
                         -T.BODYWEIGHT_LOSS_FRACTION, "falling", note, triggered),
                    1.5))

    return _weighted(
        cause_id="nutrition",
        label="Under-fueling",
        fix=("Eat enough to support training: aim for at least maintenance "
             "calories (a slight surplus for strength/size goals) and ~1.6–2.2 "
             "g protein per kg body weight, with a meal around your workout."),
        weighted_signals=signals,
    )


# ---------------------------------------------------------------------------
# RULE 4 — PROGRAMMING STALENESS
# "You've done the exact same thing for too long."
# Fires when the rep scheme (and usually the load) hasn't varied for several
# weeks. Often co-exists with insufficient stimulus, but the fix is different:
# introduce variation, not just more effort.
# ---------------------------------------------------------------------------

def rule_staleness(w: WindowStats) -> Cause:
    signals: list = []

    if w.routine_age_weeks is not None:
        # DIRECT (routine-driven): read the plan itself rather than inferring it
        # from unchanged logs.

        # Signal: the routine (the plan) has gone unchanged too long (weight 1.5).
        triggered = w.routine_age_weeks >= T.STALE_ROUTINE_WEEKS
        note = (f"Your routine hasn't changed in {w.routine_age_weeks:.0f} weeks "
                f"(≥{T.STALE_ROUTINE_WEEKS:.0f}) — same plan, same stimulus.") \
            if triggered else ""
        signals.append((_sig("routine_unchanged", round(w.routine_age_weeks, 1),
                             T.STALE_ROUTINE_WEEKS, "above", note, triggered), 1.5))

        # Signal: no movement-pattern rotation for this muscle group (weight 2.0)
        # — the routine only ever trains it one way. Uses the library tags.
        if w.muscle_pattern_count is not None:
            triggered = w.muscle_pattern_count <= 1
            note = ("The routine trains this muscle group with only one movement "
                    "pattern — nothing to rotate through.") if triggered else ""
        else:
            triggered, note = False, ""
        signals.append((_sig("no_pattern_rotation", w.muscle_pattern_count, 2,
                             "below", note, triggered), 2.0))
    else:
        # INFERRED (log-only fallback): the trailing rep-scheme run heuristic,
        # used when the user has no declared routine to read from.
        no_variation = (w.stale_run_sessions >= T.STALE_SESSIONS
                        and w.stale_run_weeks >= T.STALE_WEEKS)
        note = (f"Same {w.stale_reps}-rep top set for {w.stale_run_sessions} "
                f"sessions across ~{w.stale_run_weeks:.1f} weeks with no variation.") \
            if no_variation else ""
        signals.append((_sig("no_rep_variation", w.stale_run_sessions,
                             T.STALE_SESSIONS, "above", note, no_variation), 2.0))

        same_load = w.stale_same_load and w.stale_run_sessions >= T.STALE_SESSIONS
        note = ("The working weight has also been identical every session."
                if same_load else "")
        signals.append((_sig("same_load", w.stale_same_load, True, "equal", note,
                             same_load), 0.5))

    return _weighted(
        cause_id="programming_staleness",
        label="Stale programming",
        fix=("Change the stimulus: rotate the rep range (e.g. move from 5s to "
             "8–12s or vice-versa), swap in a close variation of the lift, or "
             "run a new progression block for 4–6 weeks."),
        weighted_signals=signals,
    )


# ---------------------------------------------------------------------------
# RULE 5 — TECHNIQUE / GRINDING
# "You're maxing effort but the bar won't move — likely a sticking point."
# Fires when RPE is at grind level (>=9) with no weight increase. Distinct from
# fatigue: here recovery may be fine, but the rep itself is technically failing
# at a specific point in the range.
# ---------------------------------------------------------------------------

def rule_technique(w: WindowStats) -> Cause:
    signals: list = []

    if w.max_rpe is not None and w.load_flat:
        triggered = w.max_rpe >= T.RPE_GRIND
        note = (f"Sets are grinding at RPE {w.max_rpe:.1f} (≥{T.RPE_GRIND}) "
                f"with no weight increase — suggests a technical sticking point "
                f"rather than simply needing to push harder.") if triggered else ""
    else:
        triggered, note = False, ""
    signals.append((_sig("grinding", w.max_rpe, T.RPE_GRIND, "above", note,
                         triggered), 2.0))

    return _weighted(
        cause_id="technique",
        label="Technique / sticking point",
        fix=("Target the sticking point: add pause reps or tempo work at the "
             "failing range, drop ~10% and rebuild with crisp technique, or add "
             "an accessory that trains the weak position."),
        weighted_signals=signals,
    )


# The ordered list of every rule the engine runs. Add new causes here.
ALL_RULES = [
    rule_insufficient_stimulus,
    rule_fatigue,
    rule_nutrition,
    rule_staleness,
    rule_technique,
]
