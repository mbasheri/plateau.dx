/* Plateau Diagnosis Fitness Tracker — frontend (React 18 + htm, no build step).
 *
 * Three views: Dashboard (diagnoses + trend charts), Log Workout, Daily Check-in.
 * All data comes from the FastAPI JSON API on the same origin. Trend charts are
 * built as SVG strings and injected, which keeps them theme-aware (CSS variables)
 * and free of any JSX/SVG attribute-casing gotchas.
 */

const { useState, useEffect, useCallback } = React;
const html = htm.bind(React.createElement);

/* ----------------------------- API helper ----------------------------- */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
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
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

const round = (n, d = 1) => {
  const f = Math.pow(10, d);
  return Math.round(n * f) / f;
};

/* --------------------------- Trend chart (SVG) ------------------------- */
function buildChartSVG(series) {
  if (!series || series.length === 0) return "";
  const W = 560, H = 180;
  const pad = { l: 40, r: 16, t: 16, b: 28 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  const n = series.length;

  const vals = series.map((s) => s.est_1rm);
  let ymin = Math.min(...vals), ymax = Math.max(...vals);
  if (ymin === ymax) { ymin -= 5; ymax += 5; }
  const span = ymax - ymin;
  ymin -= span * 0.12; ymax += span * 0.12;

  const x = (i) => n === 1 ? pad.l + iw / 2 : pad.l + (iw * i) / (n - 1);
  const y = (v) => pad.t + ih * (1 - (v - ymin) / (ymax - ymin));

  // Plateau shading: from the last new-high session to the end.
  let lastHigh = -1;
  series.forEach((s, i) => { if (s.is_new_high) lastHigh = i; });
  const stalled = n - 1 - lastHigh; // sessions since last high
  let shade = "";
  if (stalled >= 3 && lastHigh >= 0) {
    const x0 = x(lastHigh);
    shade = `<rect x="${x0.toFixed(1)}" y="${pad.t}" width="${(x(n - 1) - x0).toFixed(1)}" height="${ih}" rx="3" style="fill: var(--bad); opacity: 0.09" />`;
  }

  // Axis baseline + min/max labels.
  const axis = `
    <line x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${pad.t + ih}" style="stroke: var(--border)" stroke-width="1" />
    <line x1="${pad.l}" y1="${pad.t + ih}" x2="${W - pad.r}" y2="${pad.t + ih}" style="stroke: var(--border)" stroke-width="1" />
    <text x="${pad.l - 6}" y="${y(ymax) + 4}" text-anchor="end" style="fill: var(--muted)" font-size="10">${round(ymax)}</text>
    <text x="${pad.l - 6}" y="${y(ymin) + 4}" text-anchor="end" style="fill: var(--muted)" font-size="10">${round(ymin)}</text>`;

  // Line path + area.
  const pts = series.map((s, i) => `${x(i).toFixed(1)},${y(s.est_1rm).toFixed(1)}`);
  const line = `<polyline points="${pts.join(" ")}" fill="none" style="stroke: var(--accent)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />`;

  // Points, with a native tooltip per session.
  const dots = series.map((s, i) => {
    const cx = x(i).toFixed(1), cy = y(s.est_1rm).toFixed(1);
    const tip = `${s.date} • ${round(s.top_weight)}×${s.top_set_reps}` +
      (s.avg_rpe != null ? ` @ RPE ${round(s.avg_rpe)}` : "") +
      ` • est 1RM ${round(s.est_1rm)}`;
    const style = s.is_new_high
      ? `fill: var(--accent); stroke: var(--panel)`
      : `fill: var(--panel); stroke: var(--accent)`;
    return `<circle cx="${cx}" cy="${cy}" r="${s.is_new_high ? 4.5 : 3.2}" style="${style}" stroke-width="1.8"><title>${tip}</title></circle>`;
  });

  // Sparse x-axis date labels (first, last).
  const dl = (i) => series[i].date.slice(5); // MM-DD
  const xlabels = `
    <text x="${x(0)}" y="${H - 8}" text-anchor="start" style="fill: var(--muted)" font-size="10">${dl(0)}</text>
    <text x="${x(n - 1)}" y="${H - 8}" text-anchor="end" style="fill: var(--muted)" font-size="10">${dl(n - 1)}</text>`;

  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Estimated 1RM trend">
    ${shade}${axis}${line}${dots.join("")}${xlabels}</svg>`;
}

function Chart({ series, plateau }) {
  return html`
    <div>
      <div class="chart" dangerouslySetInnerHTML=${{ __html: buildChartSVG(series) }}></div>
      <div class="chart-legend">
        <span><span class="swatch" style=${{ background: "var(--accent)" }}></span> new personal best (est. 1RM)</span>
        ${plateau && html`<span><span class="swatch" style=${{ background: "var(--bad)", opacity: 0.35 }}></span> plateau span</span>`}
      </div>
    </div>`;
}

/* ------------------------------ Report card --------------------------- */
function StatusBadge({ report }) {
  const p = report.plateau;
  if (!p.enough_data) return html`<span class="badge nodata">Not enough data</span>`;
  if (p.is_plateau) {
    const wk = p.length_weeks >= 1 ? `${Math.round(p.length_weeks)} wk` : `${p.length_sessions} sessions`;
    return html`<span class="badge plateau">● Plateau · ${wk}</span>`;
  }
  return html`<span class="badge progress">▲ Progressing</span>`;
}

function CauseCard({ cause }) {
  const fired = cause.signals.filter((s) => s.triggered);
  return html`
    <div class="cause" data-cause=${cause.id}>
      <div class="cause-head">
        <span class="label">${cause.label}</span>
        <span class="chip ${cause.confidence}">${cause.confidence}</span>
        <span class="score">signal score ${cause.score}</span>
      </div>
      <ul class="evidence">
        ${fired.map((s, i) => html`<li key=${i}>${s.note}</li>`)}
      </ul>
      <div class="fix"><b>Fix:</b> ${cause.fix}</div>
    </div>`;
}

function ReportCard({ report }) {
  const p = report.plateau;
  const isPlateau = p.enough_data && p.is_plateau;
  return html`
    <div class="card">
      <div class="card-head">
        <h2>${report.exercise.name}</h2>
        <span class="muscle">${report.exercise.muscle_group}</span>
        <div style=${{ marginLeft: "auto" }}><${StatusBadge} report=${report} /></div>
      </div>

      <p class="summary-line">${report.summary}</p>

      <${Chart} series=${p.series} plateau=${isPlateau} />

      ${isPlateau && report.causes.length > 0 && html`
        <div class="causes">
          <div class="section-title" style=${{ margin: "6px 0 2px" }}>Why — the evidence</div>
          ${report.causes.map((c, i) => html`<${CauseCard} key=${i} cause=${c} />`)}
        </div>`}
    </div>`;
}

/* ------------------------------ Dashboard ----------------------------- */
function Dashboard({ data, loading }) {
  if (loading) return html`<div class="spinner">Analyzing your logs…</div>`;
  if (!data || !data.reports.length) {
    return html`<div class="empty">No exercises logged yet. Head to <b>Log Workout</b> to add some sessions.</div>`;
  }
  const reports = data.reports;
  const plateaus = reports.filter((r) => r.plateau.enough_data && r.plateau.is_plateau);
  const progressing = reports.filter((r) => r.plateau.enough_data && !r.plateau.is_plateau);

  return html`
    <div>
      <div class="summary-strip">
        <div class="stat ${plateaus.length ? "alert" : "ok"}">
          <div class="n">${plateaus.length}</div>
          <div class="l">plateau${plateaus.length === 1 ? "" : "s"} detected</div>
        </div>
        <div class="stat ok">
          <div class="n">${progressing.length}</div>
          <div class="l">progressing well</div>
        </div>
        <div class="stat">
          <div class="n">${reports.length}</div>
          <div class="l">exercises tracked</div>
        </div>
      </div>
      ${reports.map((r, i) => html`<${ReportCard} key=${i} report=${r} />`)}
    </div>`;
}

/* ---------------------------- Log Workout ----------------------------- */
function emptySet() { return { exercise_name: "", reps: "", weight: "", rpe: "" }; }

function LogWorkout({ exercises, onSaved, toast }) {
  const [date, setDate] = useState(todayISO());
  const [rows, setRows] = useState([emptySet(), emptySet(), emptySet()]);
  const [saving, setSaving] = useState(false);

  const update = (i, k, v) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const addRow = () => setRows((rs) => [...rs, emptySet()]);
  const removeRow = (i) => setRows((rs) => rs.filter((_, j) => j !== i));

  const submit = async (e) => {
    e.preventDefault();
    const sets = rows
      .filter((r) => r.exercise_name.trim() && r.reps && r.weight)
      .map((r) => ({
        exercise_name: r.exercise_name.trim(),
        reps: parseInt(r.reps, 10),
        weight: parseFloat(r.weight),
        rpe: r.rpe ? parseFloat(r.rpe) : null,
      }));
    if (!sets.length) { toast("Add at least one complete set (exercise, reps, weight)."); return; }
    setSaving(true);
    try {
      await api("/api/sessions", { method: "POST", body: JSON.stringify({ date, sets }) });
      toast("Workout logged ✓");
      setRows([emptySet(), emptySet(), emptySet()]);
      onSaved();
    } catch (err) { toast("Error: " + err.message); }
    finally { setSaving(false); }
  };

  return html`
    <form class="card" onSubmit=${submit}>
      <div class="card-head"><h2>Log a workout</h2></div>
      <p class="help">One set per row. Add several rows for the same exercise to log multiple sets. RPE (1–10 perceived effort) is optional but sharpens the diagnosis.</p>

      <div class="row">
        <div class="field" style=${{ maxWidth: "220px" }}>
          <label>Date</label>
          <input type="date" value=${date} onChange=${(e) => setDate(e.target.value)} />
        </div>
      </div>

      <datalist id="exlist">
        ${exercises.map((ex, i) => html`<option key=${i} value=${ex.name}></option>`)}
      </datalist>

      ${rows.map((r, i) => html`
        <div class="set-row" key=${i}>
          <div class="field">
            ${i === 0 && html`<label>Exercise</label>`}
            <input list="exlist" placeholder="e.g. Bench Press" value=${r.exercise_name}
              onChange=${(e) => update(i, "exercise_name", e.target.value)} />
          </div>
          <div class="field">
            ${i === 0 && html`<label>Reps</label>`}
            <input type="number" min="1" placeholder="reps" value=${r.reps}
              onChange=${(e) => update(i, "reps", e.target.value)} />
          </div>
          <div class="field">
            ${i === 0 && html`<label>Weight</label>`}
            <input type="number" min="0" step="0.5" placeholder="weight" value=${r.weight}
              onChange=${(e) => update(i, "weight", e.target.value)} />
          </div>
          <div class="field">
            ${i === 0 && html`<label>RPE</label>`}
            <input type="number" min="1" max="10" step="0.5" placeholder="—" value=${r.rpe}
              onChange=${(e) => update(i, "rpe", e.target.value)} />
          </div>
          <button type="button" class="link" title="Remove set" onClick=${() => removeRow(i)}>✕</button>
        </div>`)}

      <div class="row" style=${{ marginTop: "6px" }}>
        <button type="button" class="btn ghost" onClick=${addRow}>+ Add set</button>
        <div style=${{ marginLeft: "auto" }}>
          <button type="submit" class="btn" disabled=${saving}>${saving ? "Saving…" : "Save workout"}</button>
        </div>
      </div>
    </form>`;
}

/* --------------------------- Daily Check-in --------------------------- */
function DailyCheckin({ onSaved, toast }) {
  const [f, setF] = useState({ date: todayISO(), sleep_hours: "", stress: "3", body_weight: "", nutrition: "enough", notes: "" });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api("/api/checkins", {
        method: "POST",
        body: JSON.stringify({
          date: f.date,
          sleep_hours: f.sleep_hours ? parseFloat(f.sleep_hours) : null,
          stress: f.stress ? parseInt(f.stress, 10) : null,
          body_weight: f.body_weight ? parseFloat(f.body_weight) : null,
          nutrition: f.nutrition || null,
          notes: f.notes || null,
        }),
      });
      toast("Check-in saved ✓");
      onSaved();
    } catch (err) { toast("Error: " + err.message); }
    finally { setSaving(false); }
  };

  return html`
    <form class="card" onSubmit=${submit}>
      <div class="card-head"><h2>Daily check-in</h2></div>
      <p class="help">Lightweight lifestyle inputs. These are what let the engine explain <i>why</i> a lift stalled. One entry per day (re-saving a date updates it).</p>

      <div class="row">
        <div class="field" style=${{ maxWidth: "200px" }}>
          <label>Date</label>
          <input type="date" value=${f.date} onChange=${(e) => set("date", e.target.value)} />
        </div>
        <div class="field">
          <label>Sleep (hours)</label>
          <input type="number" min="0" max="24" step="0.1" placeholder="e.g. 7.5" value=${f.sleep_hours}
            onChange=${(e) => set("sleep_hours", e.target.value)} />
        </div>
        <div class="field">
          <label>Stress (1 calm – 5 high)</label>
          <select value=${f.stress} onChange=${(e) => set("stress", e.target.value)}>
            ${[1, 2, 3, 4, 5].map((n) => html`<option key=${n} value=${String(n)}>${n}</option>`)}
          </select>
        </div>
      </div>

      <div class="row">
        <div class="field">
          <label>Body weight</label>
          <input type="number" min="0" step="0.1" placeholder="optional" value=${f.body_weight}
            onChange=${(e) => set("body_weight", e.target.value)} />
        </div>
        <div class="field">
          <label>Nutrition</label>
          <select value=${f.nutrition} onChange=${(e) => set("nutrition", e.target.value)}>
            <option value="under">Under-ate</option>
            <option value="enough">Ate enough</option>
            <option value="over">Over-ate</option>
          </select>
        </div>
        <div class="field">
          <label>Notes</label>
          <input type="text" placeholder="optional" value=${f.notes}
            onChange=${(e) => set("notes", e.target.value)} />
        </div>
      </div>

      <div class="row">
        <div style=${{ marginLeft: "auto" }}>
          <button type="submit" class="btn" disabled=${saving}>${saving ? "Saving…" : "Save check-in"}</button>
        </div>
      </div>
    </form>`;
}

/* -------------------------------- App --------------------------------- */
function App() {
  const [view, setView] = useState("dashboard");
  const [boot, setBoot] = useState({ user: null, exercises: [] });
  const [diag, setDiag] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toastMsg, setToastMsg] = useState(null);

  const toast = useCallback((m) => {
    setToastMsg(m);
    setTimeout(() => setToastMsg(null), 2600);
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [b, d] = await Promise.all([api("/api/bootstrap"), api("/api/diagnose")]);
      setBoot(b);
      setDiag(d);
    } catch (err) { toast("Load error: " + err.message); }
    finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const afterSave = useCallback(() => { loadAll(); setView("dashboard"); }, [loadAll]);

  return html`
    <div class="app">
      <header class="topbar">
        <div class="topbar-inner">
          <div class="brand">
            <h1>Plateau<span class="dot">·</span>Dx</h1>
            <span class="sub">${boot.user ? `${boot.user.display_name} · goal: ${boot.user.goal}` : "diagnose why you've stalled"}</span>
          </div>
          <nav class="tabs">
            <button class=${view === "dashboard" ? "active" : ""} onClick=${() => setView("dashboard")}>Dashboard</button>
            <button class=${view === "log" ? "active" : ""} onClick=${() => setView("log")}>Log Workout</button>
            <button class=${view === "checkin" ? "active" : ""} onClick=${() => setView("checkin")}>Daily Check-in</button>
          </nav>
        </div>
      </header>

      ${view === "dashboard" && html`<${Dashboard} data=${diag} loading=${loading} />`}
      ${view === "log" && html`<${LogWorkout} exercises=${boot.exercises} onSaved=${afterSave} toast=${toast} />`}
      ${view === "checkin" && html`<${DailyCheckin} onSaved=${afterSave} toast=${toast} />`}

      ${toastMsg && html`<div class="toast">${toastMsg}</div>`}
    </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
