# Plateau·Dx — Plateau Diagnosis Fitness Tracker

Most fitness apps chart your volume/1RM and leave you to guess *why* you've
stalled. This one **diagnoses the cause**. It ingests workout logs plus a few
lightweight daily lifestyle inputs, detects when a lift has plateaued, and runs a
**transparent, rules-based reasoning engine** that explains the likely cause(s)
with the actual evidence and a recommended fix — e.g.:

> *You've plateaued on Bench Press for 4 weeks. Likely cause: fatigue —
> sleep has averaged 6.2h and RPE has climbed while the weight stayed flat.
> Suggested fix: deload 10% for one week and prioritise sleep before adding
> volume back.*

The reasoning is deliberately **not** a black box: every verdict lists the named
signals it looked at, the real number vs. the threshold, and how the causes were
ranked.

---

## Quick start

No Node required — the frontend is React with **no build step**. You only need
Python 3.9+.

```bash
./run.sh
```

Then open **http://127.0.0.1:8000**. First run seeds a realistic demo dataset so
the dashboard is populated immediately.

<details>
<summary>Manual steps (equivalent to run.sh)</summary>

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m uvicorn server.main:app --port 8000 --reload
```
</details>

### Run the tests (the core IP)

```bash
./.venv/bin/python -m pytest
```

The engine is a pure, standalone module with a full test suite covering plateau
detection (vs. noise) and each cause rule firing correctly.

---

## Architecture

The **engine is a pure module** — no database, no web framework, no I/O. It takes
plain dataclasses in and returns a structured `DiagnosisReport` out, so it can be
tested and tuned in complete isolation. The server maps DB rows → engine types →
JSON; the engine never sees a database row.

```
engine/            ← the core IP (pure Python, no deps)
  thresholds.py      every tunable knob, in one place, heavily commented
  types.py           input/output dataclasses (fully inspectable)
  metrics.py         Epley 1RM, per-session aggregation, trend helpers
  detection.py       "is this lift plateaued?" (no cause reasoning)
  rules.py           the cause-reasoning engine (5 rules, if/then, weighted)
  diagnose.py        orchestrator: detection + rules → ranked DiagnosisReport
tests/             ← pytest suite for the engine
server/            ← FastAPI + SQLite (thin; all SQL in repository.py)
  db.py, repository.py, schemas.py, seed.py, main.py
web/               ← no-build React (vendored React 18 + htm) + SVG charts
data/fitness.db    ← SQLite file (created on first run; open it to inspect)
```

Data flow: **log → SQLite → `repository` maps rows to engine types → `engine`
diagnoses → JSON → React dashboard**. The full `DiagnosisReport` is also persisted
to `plateau_reports.report_json` so every past verdict stays inspectable.

---

## Data schema

Clean and normalized so you can see exactly what the engine saw. All weights are
**unit-agnostic to the engine** (it only ever compares a lift to its own past);
`users.weight_unit` is display-only.

| Table | Purpose | Key columns |
|---|---|---|
| `users` | one row per user (MVP seeds a single user id=1) | `weight_unit`, `goal` |
| `exercises` | movement catalog, per user | `name`, `muscle_group`, `modality` |
| `workout_sessions` | a training day | `date`, `notes` |
| `workout_sets` | individual sets | `exercise_id`, `reps`, `weight`, `rpe?` |
| `daily_checkins` | daily lifestyle inputs (1/user/date) | `sleep_hours`, `stress`, `body_weight`, `nutrition` |
| `plateau_reports` | persisted engine output | `is_plateau`, `report_json` (full diagnosis) |

**Single-user MVP:** there's no login. A `user_id` FK is on every table, so going
multi-tenant is a switch of one constant (`USER_ID` in `server/main.py`), not a
rewrite.

**Wearable-ready (not built):** device data would land in a future
`device_daily_metrics(date, source, sleep_hours, hrv, recovery_score, …)` table;
the engine's data loader would prefer device data and fall back to self-report —
no change to the tables above.

---

## How the engine works

**Detection** (`detection.py`). The unit is an *exercise-session* (one exercise's
sets on one date). Each session is reduced to an **estimated 1RM** (Epley:
`weight × (1 + reps/30)`) so the metric captures weight *and* reps. A session
only counts as a "new high" if it beats the prior best by more than a noise floor.
A lift is plateaued if the most recent *N* sessions produced no new high.

**Cause reasoning** (`rules.py`). When (and only when) a plateau is confirmed,
five rules each evaluate their signals and return a `Cause` carrying its evidence.
Causes are ranked by summed signal weight; the top 1–2 become the headline. Every
signal is recorded (fired or not) so the reasoning is fully traceable.

| Cause | Fires when (defaults) | Fix it recommends |
|---|---|---|
| **Insufficient stimulus** | effort is low (avg RPE ≤ 7, gas left) and/or no overload attempted / low volume | apply double-progression; add load or reps |
| **Fatigue / under-recovery** | low/falling sleep **+** high/rising stress **+** RPE creeping at flat load **+** high frequency | deload ~10% one week, prioritise sleep |
| **Under-fueling** | ≥40% days under-eating **or** body weight falling ≥1% during a strength plateau | hit maintenance+ calories and protein |
| **Stale programming** | same rep scheme (and load) unchanged ≥4 sessions **and** ≥4 weeks | rotate rep range / vary the lift |
| **Technique / sticking point** | RPE grinding ≥9 at flat weight, not explained by fatigue | pause/tempo work, address the weak range |

To **add a cause**, write a `rule_*(w: WindowStats) -> Cause` function and append
it to `ALL_RULES`. To **swap in an ML model later**, keep `diagnose_exercise`'s
signature and replace the rule ranking internally — the input/output contract and
the whole app around it stay the same.

---

## ⚑ Assumptions & thresholds you can tune

Everything below is a **transparent starting point, not settled science.** All of
it lives in one file — **`engine/thresholds.py`** — and the engine + its
explanations update automatically when you change a value. The test suite pins
these behaviours, so if you change a threshold and a test fails, that's the test
doing its job — update it deliberately.

| Assumption (default) | Constant | Notes |
|---|---|---|
| **5 sessions with no new high = plateau** | `PLATEAU_WINDOW_SESSIONS = 5` | tuned for ~2–3×/week per lift; use ~3 for ~1×/week. Raise → stricter/slower; lower → catches stalls sooner |
| Need ≥ **6 sessions** before judging | `MIN_SESSIONS_TO_JUDGE = 6` | otherwise "not enough data", no verdict |
| A "new high" must beat prior best by **>1.5%** | `IMPROVEMENT_NOISE_FRACTION = 0.015` | absorbs plate-rounding / day-to-day noise |
| Progression metric = **estimated 1RM (Epley)** | `detection.PRIMARY_METRIC` / `metrics.epley_1rm` | captures weight *and* reps |
| Low sleep = avg **< 6.5h**; declining = **−0.75h** | `SLEEP_LOW_HOURS`, `SLEEP_DECLINE_HOURS` | fatigue signals |
| High stress = **≥3.5/5**; rising = **+0.75** | `STRESS_HIGH`, `STRESS_RISE` | on the 1–5 self-report scale |
| RPE "creeping" = **+1.0** at flat load; grind = **≥9** | `RPE_RISE`, `RPE_GRIND` | fatigue vs. technique |
| Low effort (headroom) = avg RPE **≤7** | `RPE_HEADROOM` | primary insufficient-stimulus signal |
| Under-eating = **≥40%** of days `under` | `UNDEREAT_RATIO` | nutrition signal |
| Weight loss during strength plateau = **≥1%** | `BODYWEIGHT_LOSS_FRACTION` | only counts for strength/hypertrophy goals |
| Stale = same scheme **≥5 sessions AND ≥4 weeks** | `STALE_SESSIONS`, `STALE_WEEKS` | the weeks guard usually binds |
| High frequency = **≥3×/week** | `HIGH_FREQUENCY_PER_WEEK` | overtraining contributor |
| Confidence: high **≥3.0**, medium **≥2.0** score | `CONFIDENCE_*_SCORE` | mapped from summed signal weights |

Per-signal **weights** live next to each rule in `rules.py` (a weight only means
something relative to its siblings), also commented.

---

## Demo data

First run seeds one coherent athlete training each lift ~2×/week over ~7 weeks
(`server/seed.py`). Lifestyle inputs are global per day — as in real life — so the
story is a single plausible timeline (solid training, then ~2 weeks of
overreaching) that still showcases three different diagnoses plus two healthy
lifts:

- **Bench Press** → fatigue plateau (the headline)
- **Overhead Press** → insufficient stimulus (stalled but easy, logged while rested)
- **Barbell Row** → stale programming (identical 3×10 for ~4+ weeks)
- **Back Squat / Deadlift** → still progressing (the app shouldn't cry wolf)

Delete `data/fitness.db` to reset and re-seed.

---

## Out of scope (MVP)

Social features, wearable integrations (data model is ready for them), a native
mobile app (the web UI is responsive), and ML-based cause detection (the engine is
structured so a model could replace the rules behind the same interface).
