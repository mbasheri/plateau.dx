/* Plateau·Dx — frontend (React 18 + htm, no build step).
 * Part B visual language: engraved scientific plate. Behaviour identical to Part A.
 */

const { useState, useEffect, useCallback, useRef } = React;
const html = htm.bind(React.createElement);

const MUSCLES = ["chest", "back", "shoulders", "quads", "hamstrings", "glutes",
  "biceps", "triceps", "calves", "core", "traps", "forearms"];
const EQUIPMENT = ["barbell", "dumbbell", "cable", "machine", "bodyweight"];

/* ----------------------------- helpers -------------------------------- */
async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    let msg = res.status + " " + res.statusText;
    try { msg = (await res.text()) || msg; } catch (e) {}
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res.text();
}
function todayISO() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
const round = (n, d = 1) => { const f = Math.pow(10, d); return Math.round(n * f) / f; };
const num = (v) => (v === "" || v == null ? null : Number(v));
const repRange = (lo, hi) => (lo && hi ? `${lo}–${hi}` : lo ? `${lo}+` : "—");

/* ------------------------------ copy ---------------------------------- */
// Plain second-person diagnosis headlines; the confidence word carries doubt.
const CAUSE_HEADLINE = {
  fatigue: "You are under-recovered.",
  insufficient_stimulus: "You aren't pushing hard enough.",
  nutrition: "You aren't eating enough.",
  programming_staleness: "Your plan has gone stale.",
  technique: "You're stuck at a sticking point.",
};
const CAUSE_SHORT = {
  fatigue: "under-recovered", insufficient_stimulus: "too easy",
  nutrition: "under-eating", programming_staleness: "stale plan", technique: "sticking point",
};
const CONF_WORD = { high: "Confident.", medium: "Likely.", low: "Possible." };

// Plain evidence labels; qualifier only where it adds what the number can't.
const SIG_LABEL = {
  avg_sleep: "Sleep", sleep_trend: "Sleep trend", avg_stress: "Stress",
  stress_trend: "Stress trend", rpe_efficiency: "Effort (RPE)", frequency: "Training days",
  rpe_headroom: "Effort (RPE)", below_target_sets: "Sets vs plan",
  no_overload_attempted: "Added load or reps", low_volume: "Sets per session",
  undereating: "Days under-eating", bodyweight_loss: "Body weight",
  routine_unchanged: "Plan age", no_pattern_rotation: "Movement variety",
  no_rep_variation: "Same rep scheme", same_load: "Same weight", grinding: "Top-set effort",
};
const SIG_QUALIFIER = {
  sleep_trend: "Falling week to week", stress_trend: "Rising week to week",
  rpe_efficiency: "Same weight, feels harder", bodyweight_loss: "Dropping while training for strength",
  routine_unchanged: "No change in weeks", no_pattern_rotation: "One movement only",
  below_target_sets: "Fewer sets than planned", no_overload_attempted: "None added",
  no_rep_variation: "Same reps every time", same_load: "Weight never moved",
};
const sigLabel = (n) => SIG_LABEL[n] || n.replace(/_/g, " ");

// Severity denominator: an overage of this size fills the amber bar. Sets how
// much warm colour a finding earns, so marginal reads small and serious reads big.
const DENOM = {
  avg_sleep: 2, sleep_trend: 2, avg_stress: 1.5, stress_trend: 2, rpe_efficiency: 2,
  rpe_headroom: 2, frequency: 2, below_target_sets: 3, undereating: 0.6,
  bodyweight_loss: 0.04, routine_unchanged: 8, no_pattern_rotation: 2,
  no_rep_variation: 6, grinding: 1.5,
};

// Plain-language glosses for jargon; rendered as dotted-underline abbrs.
const GLOSS = {
  rpe: "how hard a set felt, from 1 (easy) to 10 (all-out)",
  "1rm": "the most you could lift once, estimated from your sets",
  deload: "a planned easy week to let your body recover",
  volume: "total work in a session: sets × reps × weight",
};
function GlossText({ text }) {
  if (text == null) return null;
  const parts = String(text).split(/\b(RPE|1RM|deload|volume)\b/gi);
  return parts.map((p, i) => {
    const g = GLOSS[p.toLowerCase()];
    return g ? html`<abbr key=${i} class="gloss" title=${g}>${p}</abbr>` : p;
  });
}

function sigValueText(sig) {
  const v = sig.value;
  switch (sig.name) {
    case "avg_sleep": case "sleep_trend": return `${v >= 0 ? "" : ""}${round(v)}h`;
    case "avg_stress": return `${round(v)}/5`;
    case "rpe_efficiency": case "stress_trend": return `${v >= 0 ? "+" : ""}${round(v)}`;
    case "frequency": return `${round(v)}/wk`;
    case "rpe_headroom": case "grinding": return `${round(v)}`;
    case "below_target_sets": return `${round(v)} / ${sig.threshold}`;
    case "undereating": return `${Math.round(v * 100)}%`;
    case "bodyweight_loss": return `${round(v * 100)}%`;
    case "routine_unchanged": return `${round(v)}w`;
    case "no_pattern_rotation": case "no_rep_variation": return `${v}`;
    default: return v == null ? "" : `${v}`;
  }
}
function sigThreshText(sig) {
  const t = sig.threshold;
  switch (sig.name) {
    case "avg_sleep": return `${round(t)}h`;
    case "sleep_trend": return `${round(t)}h`;
    case "avg_stress": return `${round(t)}`;
    case "frequency": case "rpe_headroom": case "grinding": return `${round(t)}`;
    case "below_target_sets": return `${t}`;
    case "undereating": return `${Math.round(t * 100)}%`;
    case "bodyweight_loss": return `${round(t * 100)}%`;
    case "routine_unchanged": return `${round(t)}w`;
    default: return t == null ? "" : `${round(t)}`;
  }
}

// Amber OVERAGE scale. Orientation is the same on every row: acceptable on the
// left, worse on the right, with the threshold tick pinned at a constant x. The
// amber bar runs from that tick to the measured marker, so its length is how far
// past the line the signal went — severity you can read without a number.
function evidenceScaleSVG(sig) {
  // boolean signals (e.g. "overload attempted") have no overage to draw — flag them
  if (typeof sig.value === "boolean" || typeof sig.threshold === "boolean") return null;
  const v = Number(sig.value), t = Number(sig.threshold);
  if (!Number.isFinite(v) || !Number.isFinite(t)) return null;
  const W = 480, H = 26, ax0 = 2, ax1 = 478, midY = 13;
  const tX = ax0 + 0.26 * (ax1 - ax0);              // threshold, same x every row
  const denom = DENOM[sig.name] || Math.abs(t) || 1;
  const sev = Math.max(0.06, Math.min(1, Math.abs(v - t) / denom));
  const vX = tX + sev * (ax1 - tX - 6);
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="severity">
    <line x1="${ax0}" y1="${midY}" x2="${ax1}" y2="${midY}" style="stroke: var(--rule)" stroke-width="1"/>
    <rect x="${tX.toFixed(1)}" y="9" width="${(vX - tX).toFixed(1)}" height="8" rx="1" style="fill: var(--amber)"/>
    <line x1="${tX.toFixed(1)}" y1="4" x2="${tX.toFixed(1)}" y2="22" style="stroke: var(--amber)" stroke-width="1.5"/>
    <circle cx="${vX.toFixed(1)}" cy="${midY}" r="4.5" style="fill: var(--emerald-vivid); stroke: var(--paper)" stroke-width="1.5"/>
  </svg>`;
}

function EvidenceItem({ sig }) {
  const svg = evidenceScaleSVG(sig);
  const q = SIG_QUALIFIER[sig.name];
  if (!svg) {
    // boolean / non-numeric signal: compact flag, no scale
    return html`<div class="ev-item">
      <div class="ev-flag">
        <span class="name"><${GlossText} text=${sigLabel(sig.name)} /></span>
        <span class="fmark">flagged</span>
      </div>
      ${q ? html`<span class="q">${q}</span>` : ""}
    </div>`;
  }
  return html`<div class="ev-item">
    <div class="row1">
      <span class="name"><${GlossText} text=${sigLabel(sig.name)} /></span>
      <span class="val">${sigValueText(sig)}</span>
    </div>
    <div class="scale" dangerouslySetInnerHTML=${{ __html: svg }}></div>
    ${q ? html`<span class="q">${q}</span>` : ""}
  </div>`;
}

/* ------------------------------ chart --------------------------------- */
function buildChartSVG(series) {
  if (!series || series.length === 0) return "";
  const W = 640, H = 150, pad = { l: 34, r: 12, t: 12, b: 22 };
  const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b, n = series.length;
  const vals = series.map((s) => s.est_1rm);
  let ymin = Math.min(...vals), ymax = Math.max(...vals);
  if (ymin === ymax) { ymin -= 5; ymax += 5; }
  const sp = ymax - ymin; ymin -= sp * 0.15; ymax += sp * 0.15;
  const x = (i) => n === 1 ? pad.l + iw / 2 : pad.l + (iw * i) / (n - 1);
  const y = (v) => pad.t + ih * (1 - (v - ymin) / (ymax - ymin));
  let lastHigh = -1; series.forEach((s, i) => { if (s.is_new_high) lastHigh = i; });
  const stalled = n - 1 - lastHigh;
  let shade = "";
  if (stalled >= 3 && lastHigh >= 0) {
    const x0 = x(lastHigh);
    shade = `<rect x="${x0.toFixed(1)}" y="${pad.t}" width="${(x(n - 1) - x0).toFixed(1)}" height="${ih}" style="fill: var(--emerald-wash)"/>`;
  }
  const axis = `
    <line x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${pad.t + ih}" style="stroke: var(--rule)" stroke-width="1"/>
    <line x1="${pad.l}" y1="${pad.t + ih}" x2="${W - pad.r}" y2="${pad.t + ih}" style="stroke: var(--rule)" stroke-width="1"/>
    <text x="${pad.l - 5}" y="${(y(ymax) + 3).toFixed(1)}" text-anchor="end" style="fill: var(--muted); font-family: var(--mono)" font-size="9">${round(ymax)}</text>
    <text x="${pad.l - 5}" y="${(y(ymin) + 3).toFixed(1)}" text-anchor="end" style="fill: var(--muted); font-family: var(--mono)" font-size="9">${round(ymin)}</text>`;
  const pts = series.map((s, i) => `${x(i).toFixed(1)},${y(s.est_1rm).toFixed(1)}`);
  const line = `<polyline points="${pts.join(" ")}" fill="none" style="stroke: var(--emerald-vivid)" stroke-width="1.5"/>`;
  const dots = series.map((s, i) => {
    const cx = x(i).toFixed(1), cy = y(s.est_1rm).toFixed(1);
    const tip = `${s.date} · ${round(s.top_weight)}×${s.top_set_reps}` +
      (s.avg_rpe != null ? ` @ RPE ${round(s.avg_rpe)}` : "") + ` · e1RM ${round(s.est_1rm)}`;
    const st = s.is_new_high ? `fill: var(--emerald-vivid); stroke: var(--paper)` : `fill: var(--paper); stroke: var(--emerald-vivid)`;
    return `<circle cx="${cx}" cy="${cy}" r="${s.is_new_high ? 3.4 : 2.6}" style="${st}" stroke-width="1"><title>${tip}</title></circle>`;
  });
  const dl = (i) => series[i].date.slice(5);
  const xl = `
    <text x="${x(0)}" y="${H - 6}" text-anchor="start" style="fill: var(--muted); font-family: var(--mono)" font-size="9">${dl(0)}</text>
    <text x="${x(n - 1)}" y="${H - 6}" text-anchor="end" style="fill: var(--muted); font-family: var(--mono)" font-size="9">${dl(n - 1)}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Estimated 1RM trend">${shade}${axis}${line}${dots.join("")}${xl}</svg>`;
}

function Chart({ series, plateau }) {
  return html`
    <div>
      <div class="chart" dangerouslySetInnerHTML=${{ __html: buildChartSVG(series) }}></div>
      <div class="chart-legend">
        <span>estimated 1RM</span>
        ${plateau && html`<span>plateau span</span>`}
      </div>
    </div>`;
}

/* ---------------------------- plateau block --------------------------- */
function PlateauBlock({ report }) {
  const [open, setOpen] = useState(true);
  const p = report.plateau;
  const top = report.causes[0];
  const rest = report.causes.slice(1);
  const fired = top ? top.signals.filter((s) => s.triggered) : [];
  const weeks = Math.max(1, Math.round(p.length_weeks));
  const headline = (top && CAUSE_HEADLINE[top.id]) || "You have plateaued.";
  const conf = (top && CONF_WORD[top.confidence]) || "";
  return html`
    <div class="block">
      <div class="dx-hero">
        <span class="kicker">${report.exercise.name} · ${report.exercise.muscle_group} · stuck ${weeks} week${weeks === 1 ? "" : "s"}</span>
        <h2 class="dx-verdict">${headline}</h2>
        <div class="dx-conf">${conf}</div>
        ${top && html`
          <div class="dx-fix">
            <span class="fix-lbl">What to do</span>
            <p><${GlossText} text=${top.fix} /></p>
          </div>`}
      </div>
      <div class="block-body">
        <div class="ev-head">
          <span class="block-meta">${p.length_sessions} sessions with no gain · window ${p.window_sessions} · ~${p.frequency_per_week}×/week</span>
          <button class="toggle" aria-expanded=${open} onClick=${() => setOpen((o) => !o)}>${open ? "hide details" : "show details"}</button>
        </div>
        ${open && html`
          <div class="ev-axis">on target ← · → over the line — amber shows how far past</div>
          <div class="ev-grid" style=${{ marginTop: "var(--sp-3)" }}>
            ${fired.map((s, i) => html`<${EvidenceItem} key=${i} sig=${s} />`)}
          </div>
          ${rest.length > 0 && html`
            <p class="block-meta" style=${{ marginTop: "var(--sp-4)" }}>
              Also possible: ${rest.map((c) => CAUSE_SHORT[c.id] || c.label.toLowerCase()).join(", ")}.
            </p>`}
          <${Chart} series=${p.series} plateau=${true} />
        `}
      </div>
    </div>`;
}

/* ------------------------------ dashboard ----------------------------- */
function Dashboard({ data, loading }) {
  if (loading) return html`<div class="wrap"><div class="spinner">reading your logs…</div></div>`;
  if (!data || !data.reports.length) {
    return html`<div class="wrap"><div class="empty">
      <span class="big">No data yet.</span>
      Set up a routine and log a few workouts. A lift needs at least four sessions before it can be judged.
    </div></div>`;
  }
  const reports = data.reports;
  const plateaus = reports.filter((r) => r.plateau.enough_data && r.plateau.is_plateau);
  return html`
    <div class="wrap">
      <div class="strip">
        <span class="strip-lbl">all lifts</span>
        ${reports.map((r, i) => {
          const p = r.plateau;
          const st = p.is_plateau
            ? (r.causes[0] ? (CAUSE_SHORT[r.causes[0].id] || "plateau") : "plateau")
            : (p.enough_data ? "on track" : "needs data");
          return html`<span class="strip-item" key=${i}>
            <span class="nm">${r.exercise.name}</span>
            <span class="st ${p.is_plateau ? "plateau" : "ok"}">${st}</span>
          </span>`;
        })}
      </div>
      ${plateaus.length === 0
        ? html`<div class="empty">No plateaus. Every tracked lift is still moving.</div>`
        : plateaus.map((r) => html`<${PlateauBlock} key=${r.exercise.id} report=${r} />`)}
    </div>`;
}

/* --------------------------- exercise picker -------------------------- */
function ExercisePicker({ onPick, onClose }) {
  const [q, setQ] = useState("");
  const [muscle, setMuscle] = useState("");
  const [equip, setEquip] = useState("");
  const [results, setResults] = useState([]);
  useEffect(() => {
    const pr = new URLSearchParams();
    if (q) pr.set("q", q); if (muscle) pr.set("muscle_group", muscle); if (equip) pr.set("equipment", equip);
    api("/api/exercises?" + pr.toString()).then(setResults).catch(() => {});
  }, [q, muscle, equip]);
  return html`
    <div class="picker">
      <div class="picker-head">
        <span class="lbl">add exercise</span>
        <button type="button" class="link" style=${{ marginLeft: "auto" }} onClick=${onClose}>close</button>
      </div>
      <div class="row">
        <div class="field"><label>search</label><input value=${q} onChange=${(e) => setQ(e.target.value)} placeholder="name" /></div>
        <div class="field"><label>muscle</label><select value=${muscle} onChange=${(e) => setMuscle(e.target.value)}>
          <option value="">any</option>${MUSCLES.map((m) => html`<option key=${m} value=${m}>${m}</option>`)}</select></div>
        <div class="field"><label>equipment</label><select value=${equip} onChange=${(e) => setEquip(e.target.value)}>
          <option value="">any</option>${EQUIPMENT.map((m) => html`<option key=${m} value=${m}>${m}</option>`)}</select></div>
      </div>
      <div class="picker-results">
        ${results.map((ex) => html`
          <button type="button" class="picker-item" key=${ex.id} onClick=${() => onPick(ex)}>
            <span>${ex.name}</span>
            <span class="meta">${ex.muscle_group} · ${ex.equipment}</span>
          </button>`)}
        ${results.length === 0 && html`<div class="help">No matches.</div>`}
      </div>
    </div>`;
}

/* --------------------------- routine setup ---------------------------- */
function RoutineSetup({ routine, templates, onSaved, toast }) {
  const [editing, setEditing] = useState(!routine);
  const [name, setName] = useState(routine ? routine.name : "My routine");
  const [srcKey, setSrcKey] = useState(routine ? routine.source_template_key : null);
  const [days, setDays] = useState(routine
    ? routine.days.map((d) => ({ label: d.label, exercises: d.exercises.map((x) => ({ ...x })) })) : null);
  const [pickerDay, setPickerDay] = useState(null);
  const [saving, setSaving] = useState(false);

  const pickTemplate = async (key) => {
    if (key === "custom") { setName("Custom routine"); setSrcKey(null); setDays([{ label: "Day 1", exercises: [] }]); return; }
    try {
      const tpl = await api("/api/templates/" + key);
      setName(tpl.name); setSrcKey(key);
      setDays(tpl.days.map((d) => ({ label: d.label, exercises: d.exercises.map((x) => ({
        exercise_id: x.exercise_id, name: x.name, muscle_group: x.muscle_group,
        target_sets: x.target_sets, target_rep_low: x.target_rep_low, target_rep_high: x.target_rep_high })) })));
    } catch (err) { toast("Error: " + err.message); }
  };
  const setDayLabel = (i, v) => setDays((ds) => ds.map((d, j) => j === i ? { ...d, label: v } : d));
  const addDay = () => setDays((ds) => [...ds, { label: `Day ${ds.length + 1}`, exercises: [] }]);
  const removeDay = (i) => setDays((ds) => ds.filter((_, j) => j !== i));
  const addExercise = (di, ex) => setDays((ds) => ds.map((d, j) => j === di
    ? { ...d, exercises: [...d.exercises, { exercise_id: ex.id, name: ex.name, muscle_group: ex.muscle_group, target_sets: 3, target_rep_low: 8, target_rep_high: 12 }] } : d));
  const updEx = (di, ei, k, v) => setDays((ds) => ds.map((d, j) => j === di
    ? { ...d, exercises: d.exercises.map((e, m) => m === ei ? { ...e, [k]: v } : e) } : d));
  const rmEx = (di, ei) => setDays((ds) => ds.map((d, j) => j === di ? { ...d, exercises: d.exercises.filter((_, m) => m !== ei) } : d));
  const moveEx = (di, ei, dir) => setDays((ds) => ds.map((d, j) => {
    if (j !== di) return d;
    const arr = [...d.exercises]; const to = ei + dir;
    if (to < 0 || to >= arr.length) return d;
    [arr[ei], arr[to]] = [arr[to], arr[ei]]; return { ...d, exercises: arr };
  }));
  const save = async () => {
    const payload = { name, source_template_key: srcKey, days: days.map((d) => ({ label: d.label,
      exercises: d.exercises.map((e) => ({ exercise_id: e.exercise_id, target_sets: num(e.target_sets),
        target_rep_low: num(e.target_rep_low), target_rep_high: num(e.target_rep_high) })) })) };
    if (!payload.days.some((d) => d.exercises.length)) { toast("Add at least one exercise."); return; }
    setSaving(true);
    try { await api("/api/routine", { method: "PUT", body: JSON.stringify(payload) });
      toast("Routine saved"); setEditing(false); onSaved();
    } catch (err) { toast("Error: " + err.message); } finally { setSaving(false); }
  };

  if (!editing && routine) {
    return html`
      <div class="wrap">
        <div class="plate">
          <div class="margin"><span class="lbl">active routine</span><span class="lbl">${routine.days.length} days</span></div>
          <div>
            <div class="plan-day-head" style=${{ borderBottom: "none", marginBottom: 0 }}>
              <h3 class="exercise-name">${routine.name}</h3>
              <button class="link" style=${{ marginLeft: "auto" }} onClick=${() => setEditing(true)}>edit</button>
            </div>
            <p class="help">The active plan. The engine compares what you log against these targets.</p>
            ${routine.days.map((d, i) => html`
              <div class="plan-day" key=${i}>
                <div class="plan-day-head"><h3>${d.label}</h3></div>
                ${d.exercises.map((e, j) => html`
                  <div class="plan-row" key=${j}>
                    <span>${e.name}</span>
                    <span class="pg">${e.muscle_group}</span>
                    <span class="pt">${e.target_sets || "—"} × ${repRange(e.target_rep_low, e.target_rep_high)}</span>
                  </div>`)}
              </div>`)}
          </div>
        </div>
      </div>`;
  }

  return html`
    <div class="wrap">
      <div class="plate">
        <div class="margin"><span class="lbl">${routine ? "edit" : "new"} routine</span></div>
        <div>
          <p class="help">Pick a split to start from, then adjust days and exercises. The plan is what makes the diagnosis measurable.</p>
          <div class="template-row">
            ${templates.map((t) => html`<button type="button" class="btn ghost" key=${t.key} onClick=${() => pickTemplate(t.key)}>${t.name} · ${t.num_days}d</button>`)}
            <button type="button" class="btn ghost" onClick=${() => pickTemplate("custom")}>custom</button>
          </div>
          ${routine && html`<button class="link" style=${{ marginTop: "var(--sp-3)" }} onClick=${() => setEditing(false)}>cancel</button>`}
        </div>
      </div>

      ${days && html`
        <div class="plate">
          <div class="margin"><span class="lbl">name</span></div>
          <div><div class="field" style=${{ maxWidth: "320px" }}><label>routine name</label>
            <input value=${name} onChange=${(e) => setName(e.target.value)} /></div></div>
        </div>
        ${days.map((d, di) => html`
          <div class="plate" key=${di}>
            <div class="margin"><span class="lbl">day ${di + 1}</span></div>
            <div>
              <div class="plan-day-head">
                <input class="day-label" value=${d.label} onChange=${(e) => setDayLabel(di, e.target.value)} />
                <button class="link" style=${{ marginLeft: "auto" }} onClick=${() => removeDay(di)}>remove day</button>
              </div>
              ${d.exercises.map((e, ei) => html`
                <div class="edit-ex" key=${ei}>
                  <div class="nm">${e.name} <span class="pg mono">${e.muscle_group}</span></div>
                  <div class="field"><label>sets</label><input type="number" min="1" max="20" value=${e.target_sets ?? ""} onChange=${(ev) => updEx(di, ei, "target_sets", ev.target.value)} /></div>
                  <div class="field"><label>rep lo</label><input type="number" min="1" value=${e.target_rep_low ?? ""} onChange=${(ev) => updEx(di, ei, "target_rep_low", ev.target.value)} /></div>
                  <div class="field"><label>rep hi</label><input type="number" min="1" value=${e.target_rep_high ?? ""} onChange=${(ev) => updEx(di, ei, "target_rep_high", ev.target.value)} /></div>
                  <div class="acts">
                    <button class="link" title="up" onClick=${() => moveEx(di, ei, -1)}>↑</button>
                    <button class="link" title="down" onClick=${() => moveEx(di, ei, 1)}>↓</button>
                    <button class="link" title="remove" onClick=${() => rmEx(di, ei)}>✕</button>
                  </div>
                </div>`)}
              <button type="button" class="btn ghost small" style=${{ marginTop: "var(--sp-3)" }} onClick=${() => setPickerDay(di)}>add exercise</button>
              ${pickerDay === di && html`<${ExercisePicker} onPick=${(ex) => { addExercise(di, ex); setPickerDay(null); }} onClose=${() => setPickerDay(null)} />`}
            </div>
          </div>`)}
        <div class="plate">
          <div class="margin"></div>
          <div class="row">
            <button type="button" class="btn ghost" onClick=${addDay}>add day</button>
            <div style=${{ marginLeft: "auto" }}><button type="button" class="btn" disabled=${saving} onClick=${save}>${saving ? "saving…" : "save routine"}</button></div>
          </div>
        </div>`}
    </div>`;
}

/* ---------------------------- day-based log --------------------------- */
function emptySet() { return { weight: "", reps: "", rpe: "" }; }
function blocksFromDay(day) {
  return (day.exercises || []).map((ex) => ({
    exercise_id: ex.exercise_id, name: ex.name, target_sets: ex.target_sets,
    target_rep_low: ex.target_rep_low, target_rep_high: ex.target_rep_high, include: true,
    sets: Array.from({ length: ex.target_sets || 3 }, emptySet),
  }));
}

function DayLog({ routine, onSaved, toast }) {
  const [date, setDate] = useState(todayISO());
  const [dayId, setDayId] = useState("");
  const [blocks, setBlocks] = useState([]);
  const [picker, setPicker] = useState(false);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    api("/api/routine/next-day").then((day) => {
      if (day) { setDayId(String(day.id)); setBlocks(blocksFromDay(day)); }
      else if (routine.days[0]) { setDayId(String(routine.days[0].id)); setBlocks(blocksFromDay(routine.days[0])); }
    }).catch(() => {});
  }, [routine]);
  const selectDay = (id) => {
    setDayId(id);
    if (id === "") { setBlocks([]); return; }
    const day = routine.days.find((d) => String(d.id) === String(id));
    if (day) setBlocks(blocksFromDay(day));
  };
  const toggle = (bi) => setBlocks((bs) => bs.map((b, i) => i === bi ? { ...b, include: !b.include } : b));
  const setSet = (bi, si, k, v) => setBlocks((bs) => bs.map((b, i) => i === bi ? { ...b, sets: b.sets.map((s, j) => j === si ? { ...s, [k]: v } : s) } : b));
  const addSet = (bi) => setBlocks((bs) => bs.map((b, i) => i === bi ? { ...b, sets: [...b.sets, emptySet()] } : b));
  const rmSet = (bi, si) => setBlocks((bs) => bs.map((b, i) => i === bi ? { ...b, sets: b.sets.filter((_, j) => j !== si) } : b));
  const addBlock = (ex) => setBlocks((bs) => [...bs, { exercise_id: ex.id, name: ex.name, target_sets: null, target_rep_low: null, target_rep_high: null, include: true, sets: [emptySet(), emptySet(), emptySet()] }]);
  const submit = async (e) => {
    e.preventDefault();
    const sets = [];
    blocks.filter((b) => b.include).forEach((b) => b.sets.forEach((s) => {
      if (s.reps && s.weight) sets.push({ exercise_id: b.exercise_id, reps: parseInt(s.reps, 10), weight: parseFloat(s.weight), rpe: s.rpe ? parseFloat(s.rpe) : null });
    }));
    if (!sets.length) { toast("Enter at least one set."); return; }
    setSaving(true);
    try { await api("/api/sessions", { method: "POST", body: JSON.stringify({ date, routine_day_id: dayId ? parseInt(dayId, 10) : null, sets }) });
      toast("Workout logged"); onSaved();
    } catch (err) { toast("Error: " + err.message); } finally { setSaving(false); }
  };
  return html`
    <div class="wrap"><div class="plate">
      <div class="margin"><span class="lbl">log</span><span class="lbl">${date.slice(5)}</span></div>
      <form onSubmit=${submit}>
        <p class="help">The next day in your rotation is filled in. Change the day if needed, enter what you did, uncheck anything you skipped, and add off-plan lifts below.</p>
        <div class="row" style=${{ marginTop: "var(--sp-4)" }}>
          <div class="field" style=${{ maxWidth: "180px" }}><label>date</label><input type="date" value=${date} onChange=${(e) => setDate(e.target.value)} /></div>
          <div class="field" style=${{ maxWidth: "220px" }}><label>day</label>
            <select value=${dayId} onChange=${(e) => selectDay(e.target.value)}>
              ${routine.days.map((d) => html`<option key=${d.id} value=${String(d.id)}>${d.label}</option>`)}
              <option value="">blank (off-plan)</option>
            </select></div>
        </div>
        <div style=${{ marginTop: "var(--sp-4)" }}>
          ${blocks.map((b, bi) => html`
            <div class="log-block ${b.include ? "" : "skipped"}" key=${bi}>
              <div class="log-block-head">
                <label class="chk"><input type="checkbox" style=${{ width: "auto" }} checked=${b.include} onChange=${() => toggle(bi)} /> ${b.name}</label>
                ${b.target_sets ? html`<span class="target">target ${b.target_sets} × ${repRange(b.target_rep_low, b.target_rep_high)}</span>` : html`<span class="target">off-plan</span>`}
              </div>
              ${b.include && b.sets.map((s, si) => html`
                <div class="set-row" key=${si}>
                  <div class="field">${si === 0 && html`<label>weight</label>`}<input type="number" min="0" step="0.5" placeholder="weight" value=${s.weight} onChange=${(e) => setSet(bi, si, "weight", e.target.value)} /></div>
                  <div class="field">${si === 0 && html`<label>reps</label>`}<input type="number" min="1" placeholder="reps" value=${s.reps} onChange=${(e) => setSet(bi, si, "reps", e.target.value)} /></div>
                  <div class="field">${si === 0 && html`<label>RPE</label>`}<input type="number" min="1" max="10" step="0.5" placeholder="—" value=${s.rpe} onChange=${(e) => setSet(bi, si, "rpe", e.target.value)} /></div>
                  <button type="button" class="link" title="remove set" onClick=${() => rmSet(bi, si)}>✕</button>
                </div>`)}
              ${b.include && html`<button type="button" class="btn ghost small" onClick=${() => addSet(bi)}>add set</button>`}
            </div>`)}
        </div>
        <div class="row" style=${{ marginTop: "var(--sp-4)" }}>
          <button type="button" class="btn ghost" onClick=${() => setPicker(true)}>add off-plan exercise</button>
          <div style=${{ marginLeft: "auto" }}><button type="submit" class="btn" disabled=${saving}>${saving ? "saving…" : "save workout"}</button></div>
        </div>
        ${picker && html`<${ExercisePicker} onPick=${(ex) => { addBlock(ex); setPicker(false); }} onClose=${() => setPicker(false)} />`}
      </form>
    </div></div>`;
}

function FreeFormLog({ exercises, onSaved, toast }) {
  const [date, setDate] = useState(todayISO());
  const [rows, setRows] = useState([{ exercise_name: "", ...emptySet() }, { exercise_name: "", ...emptySet() }, { exercise_name: "", ...emptySet() }]);
  const [saving, setSaving] = useState(false);
  const upd = (i, k, v) => setRows((rs) => rs.map((r, j) => j === i ? { ...r, [k]: v } : r));
  const submit = async (e) => {
    e.preventDefault();
    const sets = rows.filter((r) => r.exercise_name.trim() && r.reps && r.weight).map((r) => ({
      exercise_name: r.exercise_name.trim(), reps: parseInt(r.reps, 10), weight: parseFloat(r.weight), rpe: r.rpe ? parseFloat(r.rpe) : null }));
    if (!sets.length) { toast("Add at least one complete set."); return; }
    setSaving(true);
    try { await api("/api/sessions", { method: "POST", body: JSON.stringify({ date, sets }) }); toast("Workout logged"); onSaved(); }
    catch (err) { toast("Error: " + err.message); } finally { setSaving(false); }
  };
  return html`
    <div class="wrap"><div class="plate">
      <div class="margin"><span class="lbl">log</span></div>
      <form onSubmit=${submit}>
        <p class="help">No routine yet, so logging is free-form. Set up a routine to log against a plan and unlock the volume-vs-plan check.</p>
        <div class="row" style=${{ marginTop: "var(--sp-4)" }}><div class="field" style=${{ maxWidth: "180px" }}><label>date</label><input type="date" value=${date} onChange=${(e) => setDate(e.target.value)} /></div></div>
        <datalist id="exlist">${exercises.map((ex, i) => html`<option key=${i} value=${ex.name}></option>`)}</datalist>
        <div style=${{ marginTop: "var(--sp-4)" }}>
          ${rows.map((r, i) => html`
            <div class="set-row wide" key=${i}>
              <div class="field">${i === 0 && html`<label>exercise</label>`}<input list="exlist" placeholder="e.g. Bench Press" value=${r.exercise_name} onChange=${(e) => upd(i, "exercise_name", e.target.value)} /></div>
              <div class="field">${i === 0 && html`<label>weight</label>`}<input type="number" min="0" step="0.5" placeholder="weight" value=${r.weight} onChange=${(e) => upd(i, "weight", e.target.value)} /></div>
              <div class="field">${i === 0 && html`<label>reps</label>`}<input type="number" min="1" placeholder="reps" value=${r.reps} onChange=${(e) => upd(i, "reps", e.target.value)} /></div>
              <div class="field">${i === 0 && html`<label>RPE</label>`}<input type="number" min="1" max="10" step="0.5" placeholder="—" value=${r.rpe} onChange=${(e) => upd(i, "rpe", e.target.value)} /></div>
            </div>`)}
        </div>
        <div class="row" style=${{ marginTop: "var(--sp-4)" }}>
          <button type="button" class="btn ghost" onClick=${() => setRows((rs) => [...rs, { exercise_name: "", ...emptySet() }])}>add row</button>
          <div style=${{ marginLeft: "auto" }}><button type="submit" class="btn" disabled=${saving}>${saving ? "saving…" : "save workout"}</button></div>
        </div>
      </form>
    </div></div>`;
}

function LogWorkout({ routine, exercises, onSaved, toast }) {
  return routine ? html`<${DayLog} routine=${routine} onSaved=${onSaved} toast=${toast} />`
    : html`<${FreeFormLog} exercises=${exercises} onSaved=${onSaved} toast=${toast} />`;
}

/* --------------------------- daily check-in --------------------------- */
function DailyCheckin({ onSaved, toast }) {
  const [f, setF] = useState({ date: todayISO(), sleep_hours: "", stress: "3", body_weight: "", nutrition: "enough", notes: "" });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const submit = async (e) => {
    e.preventDefault(); setSaving(true);
    try { await api("/api/checkins", { method: "POST", body: JSON.stringify({ date: f.date, sleep_hours: num(f.sleep_hours), stress: num(f.stress), body_weight: num(f.body_weight), nutrition: f.nutrition || null, notes: f.notes || null }) });
      toast("Check-in saved"); onSaved();
    } catch (err) { toast("Error: " + err.message); } finally { setSaving(false); }
  };
  return html`
    <div class="wrap"><div class="plate">
      <div class="margin"><span class="lbl">check-in</span><span class="lbl">${f.date.slice(5)}</span></div>
      <form onSubmit=${submit}>
        <p class="help">Daily inputs the engine uses to explain a stall. One entry per day; saving a date again replaces it.</p>
        <div class="row" style=${{ marginTop: "var(--sp-4)" }}>
          <div class="field" style=${{ maxWidth: "180px" }}><label>date</label><input type="date" value=${f.date} onChange=${(e) => set("date", e.target.value)} /></div>
          <div class="field"><label>sleep (hours)</label><input type="number" min="0" max="24" step="0.1" placeholder="7.5" value=${f.sleep_hours} onChange=${(e) => set("sleep_hours", e.target.value)} /></div>
          <div class="field"><label>stress (1 calm – 5 high)</label><select value=${f.stress} onChange=${(e) => set("stress", e.target.value)}>${[1, 2, 3, 4, 5].map((n) => html`<option key=${n} value=${String(n)}>${n}</option>`)}</select></div>
        </div>
        <div class="row" style=${{ marginTop: "var(--sp-4)" }}>
          <div class="field"><label>body weight</label><input type="number" min="0" step="0.1" placeholder="optional" value=${f.body_weight} onChange=${(e) => set("body_weight", e.target.value)} /></div>
          <div class="field"><label>nutrition</label><select value=${f.nutrition} onChange=${(e) => set("nutrition", e.target.value)}>
            <option value="under">under-ate</option><option value="enough">ate enough</option><option value="over">over-ate</option></select></div>
          <div class="field"><label>notes</label><input type="text" placeholder="optional" value=${f.notes} onChange=${(e) => set("notes", e.target.value)} /></div>
        </div>
        <div class="row" style=${{ marginTop: "var(--sp-5)" }}><div style=${{ marginLeft: "auto" }}><button type="submit" class="btn" disabled=${saving}>${saving ? "saving…" : "save check-in"}</button></div></div>
      </form>
    </div></div>`;
}

/* -------------------------------- app --------------------------------- */
function useTheme() {
  const [theme, setTheme] = useState(() =>
    window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  return [theme, setTheme];
}

function App() {
  const [view, setView] = useState("overview");
  const [boot, setBoot] = useState({ user: null, exercises: [], has_routine: false });
  const [diag, setDiag] = useState(null);
  const [routine, setRoutine] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toastMsg, setToastMsg] = useState(null);
  const [theme, setTheme] = useTheme();

  const toast = useCallback((m) => { setToastMsg(m); setTimeout(() => setToastMsg(null), 2600); }, []);
  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [b, d, r, t] = await Promise.all([api("/api/bootstrap"), api("/api/diagnose"), api("/api/routine"), api("/api/templates")]);
      setBoot(b); setDiag(d); setRoutine(r); setTemplates(t);
    } catch (err) { toast("Load error: " + err.message); } finally { setLoading(false); }
  }, [toast]);
  useEffect(() => { loadAll(); }, [loadAll]);
  const reload = useCallback(() => { loadAll(); }, [loadAll]);
  const afterSave = useCallback(() => { loadAll(); setView("overview"); }, [loadAll]);

  const tabs = [["overview", "Overview"], ["routine", "Routine"], ["log", "Log"], ["checkin", "Check-in"]];

  return html`
    <div>
      <header class="masthead">
        <div class="masthead-in">
          <span class="wordmark">Plateau<span class="mid">·</span>Dx</span>
          <span class="who mono" style=${{ fontSize: "11px", letterSpacing: "0.06em" }}>
            ${boot.user ? `${boot.user.display_name} · ${boot.user.goal}` : ""}</span>
          <nav class="tabs">
            ${tabs.map(([id, label]) => html`<button key=${id} class=${view === id ? "active" : ""} onClick=${() => setView(id)}>${label}</button>`)}
            <button class="theme-toggle" onClick=${() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="toggle theme">${theme === "dark" ? "light" : "dark"}</button>
          </nav>
        </div>
      </header>

      <main>
        ${view === "overview" && html`<${Dashboard} data=${diag} loading=${loading} />`}
        ${view === "routine" && html`<${RoutineSetup} routine=${routine} templates=${templates} onSaved=${reload} toast=${toast} />`}
        ${view === "log" && html`<${LogWorkout} routine=${routine} exercises=${boot.exercises} onSaved=${afterSave} toast=${toast} />`}
        ${view === "checkin" && html`<${DailyCheckin} onSaved=${afterSave} toast=${toast} />`}
      </main>

      ${toastMsg && html`<div class="toast">${toastMsg}</div>`}
    </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
