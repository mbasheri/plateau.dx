/* Plateau·Dx — frontend (React 18 + htm, no build step).
 * v2 redesign: light + colorful, Apple-Health-style charts, simplified diagnosis,
 * reusable science dropdown, TDEE calculator, demo health summary.
 */

const { useState, useEffect, useCallback } = React;
const html = htm.bind(React.createElement);

// Frontend and API share one Vercel origin, so every call is a relative /api/*
// path — no base URL, no CORS, no build-time env injection.

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
const commafy = (n) => Math.round(n).toLocaleString("en-US");

/* -------- go home (wordmark): always route to the marketing page ------- */
function goHome(e) { if (e) e.preventDefault(); window.location.href = "/"; }

/* ------------------------------ copy ---------------------------------- */
// Per-cause accent color (consistent app-wide: each metric owns one hue).
const CAUSE_COLOR = {
  fatigue: "var(--c-teal)", insufficient_stimulus: "var(--c-pink)",
  nutrition: "var(--c-orange)", programming_staleness: "var(--c-orange-deep)",
  technique: "var(--c-red)",
};
// The short, direct action that completes "Lift: ___".
const CAUSE_ACTION = {
  fatigue: "recover more", insufficient_stimulus: "push harder",
  nutrition: "eat more", programming_staleness: "switch it up",
  technique: "beat the sticking point",
};
const CAUSE_EMOJI = {
  fatigue: "🛌", insufficient_stimulus: "💪", nutrition: "🍽️",
  programming_staleness: "🔄", technique: "🎯",
};
const CAUSE_SHORT = {
  fatigue: "low recovery", insufficient_stimulus: "too easy",
  nutrition: "under-eating", programming_staleness: "stale plan", technique: "sticking point",
};
const CAUSE_THEME = {
  fatigue: "recovery", insufficient_stimulus: "training intensity",
  nutrition: "nutrition", programming_staleness: "stale programming", technique: "technique",
};
const CONF_WORD = { high: "Confident", medium: "Likely", low: "Possible" };

// The reusable "The science" content: research finding + citation + what to do.
const SCIENCE = {
  fatigue: {
    finding: "Sleep loss cripples strength recovery — under about 6 hours a night, perceived effort climbs and force output drops, so the same weight feels heavier.",
    cite: "Knowles et al., 2018, Journal of Sports Sciences — sleep & strength performance.",
    todo: "Aim for 7–9 h and deload ~10% for a week; only rebuild load once that weight feels easier again.",
  },
  insufficient_stimulus: {
    finding: "Muscle adapts in response to hard sets — the reps close to failure do most of the work. Leaving several reps in the tank blunts the signal to grow stronger.",
    cite: "Refalo et al., 2023, Sports Medicine — proximity to failure & hypertrophy.",
    todo: "Take your top sets to RPE 8–9, and add a rep or a little load each week (double progression).",
  },
  nutrition: {
    finding: "You can't build strength in a meaningful energy deficit, and muscle repair needs roughly 1.6–2.2 g of protein per kg of bodyweight per day.",
    cite: "Morton et al., 2018, British Journal of Sports Medicine — protein meta-analysis.",
    todo: "Eat at or slightly above maintenance and hit your protein target, especially around training.",
  },
  programming_staleness: {
    finding: "The body adapts to a repeated stimulus and stops responding — the 'principle of accommodation.' Rotating lifts and rep ranges renews the stimulus.",
    cite: "Zatsiorsky & Kraemer, Science and Practice of Strength Training.",
    todo: "Change one variable every 4–6 weeks: swap in a variation or shift your rep range (e.g. 5s → 8–12s).",
  },
  technique: {
    finding: "Repeatedly failing at the same point in a lift usually reflects a region-specific strength deficit, not global fatigue — a true sticking point.",
    cite: "Kompf & Arandjelović, 2016, Sports Medicine — sticking points in resistance training.",
    todo: "Add pause or tempo reps at the failing range, or an accessory that trains the weak position.",
  },
  tdee: {
    finding: "The Mifflin-St Jeor equation is the most accurate common predictor of resting metabolic rate for the general population.",
    cite: "Mifflin & St Jeor, 1990, American Journal of Clinical Nutrition.",
    todo: "Eat around your TDEE to maintain; add ~300–500 kcal/day to gain, or subtract it to lose.",
  },
};

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

// Each signal's metric hue (matches the palette assignment everywhere else).
const SIG_COLOR = {
  avg_sleep: "var(--c-teal)", sleep_trend: "var(--c-teal)",
  avg_stress: "var(--c-orange-deep)", stress_trend: "var(--c-orange-deep)",
  rpe_efficiency: "var(--c-pink)", rpe_headroom: "var(--c-pink)", grinding: "var(--c-pink)",
  frequency: "var(--c-red)", below_target_sets: "var(--c-red)", low_volume: "var(--c-red)",
  no_overload_attempted: "var(--c-red)", no_rep_variation: "var(--c-red)", same_load: "var(--c-red)",
  undereating: "var(--c-orange)", bodyweight_loss: "var(--c-orange)",
  routine_unchanged: "var(--c-orange-deep)", no_pattern_rotation: "var(--c-orange-deep)",
};
const sigColor = (n) => SIG_COLOR[n] || "var(--c-orange-deep)";

// Severity denominator: an overage of this size fills the bar.
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
    case "avg_sleep": case "sleep_trend": return `${round(v)}h`;
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

/* --------------------- Apple-Health-style smooth chart ---------------- */
// Catmull-Rom → cubic bezier so the line curves smoothly instead of zig-zagging.
function smoothPath(pts) {
  if (!pts.length) return "";
  if (pts.length < 3) return "M" + pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" L");
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  const t = 0.16;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    const c1x = p1[0] + (p2[0] - p0[0]) * t, c1y = p1[1] + (p2[1] - p0[1]) * t;
    const c2x = p2[0] - (p3[0] - p1[0]) * t, c2y = p2[1] - (p3[1] - p1[1]) * t;
    d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
}

let _gradSeq = 0;
// Soft gradient-filled line chart: rounded caps, one faint midline, colored
// end-dot with its value. `color` is a raw hex so we can build a matching gradient.
function healthChartSVG(values, opts) {
  const o = opts || {};
  const color = o.color || "#F20544";
  const unit = o.unit || "";
  const dec = o.decimals == null ? 0 : o.decimals;
  const H = o.height || 150;
  const values2 = values.filter((v) => v != null && Number.isFinite(v));
  if (values2.length === 0) return "";
  const W = 640, pad = { l: 10, r: 46, t: 16, b: 14 };
  const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b, n = values2.length;
  let ymin = Math.min(...values2), ymax = Math.max(...values2);
  if (ymin === ymax) { ymin -= 1; ymax += 1; }
  const sp = ymax - ymin; ymin -= sp * 0.2; ymax += sp * 0.28;
  const X = (i) => (n === 1 ? pad.l + iw / 2 : pad.l + (iw * i) / (n - 1));
  const Y = (v) => pad.t + ih * (1 - (v - ymin) / (ymax - ymin));
  const pts = values2.map((v, i) => [X(i), Y(v)]);
  const gid = "hc" + (_gradSeq++);
  const line = smoothPath(pts);
  const area = `${line} L${X(n - 1).toFixed(1)},${(pad.t + ih).toFixed(1)} L${X(0).toFixed(1)},${(pad.t + ih).toFixed(1)} Z`;
  const midY = (pad.t + ih * 0.5).toFixed(1);
  const last = pts[n - 1], lastV = values2[n - 1];
  const label = `${round(lastV, dec).toLocaleString("en-US")}${unit}`;
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="trend">
    <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${color}" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs>
    <line x1="${pad.l}" y1="${midY}" x2="${W - pad.r}" y2="${midY}" stroke="var(--rule)" stroke-width="1"/>
    <path d="${area}" fill="url(#${gid})"/>
    <path d="${line}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="8" fill="${color}" opacity="0.16"/>
    <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="4.5" fill="${color}"/>
    <text x="${(last[0] + 10).toFixed(1)}" y="${(last[1] + 4).toFixed(1)}" fill="${color}" font-size="15" font-weight="800" font-family="Nunito, sans-serif">${label}</text>
  </svg>`;
}

/* --------------------------- calorie ring ----------------------------- */
// Two concentric rings (Apple activity-ring style): outer = eaten, inner = burned,
// each as a fraction of the larger of the two. Center shows the net.
function calorieRingSVG(eaten, burned) {
  const size = 190, c = size / 2, sw = 17, gap = 7;
  const rO = c - sw / 2 - 2, rI = rO - sw - gap;
  const goal = Math.max(eaten, burned, 1);
  const CO = 2 * Math.PI * rO, CI = 2 * Math.PI * rI;
  const fO = Math.min(1, eaten / goal), fI = Math.min(1, burned / goal);
  const net = eaten - burned;
  const netLabel = net >= 0 ? "surplus" : "deficit";
  const netColor = net >= 0 ? "var(--c-orange)" : "var(--c-teal)";
  const ring = (r, C, frac, col) => `
    <circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="var(--surface-2)" stroke-width="${sw}"/>
    <circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${col}" stroke-width="${sw}"
      stroke-linecap="round" stroke-dasharray="${(C * frac).toFixed(1)} ${C.toFixed(1)}"
      transform="rotate(-90 ${c} ${c})"/>`;
  return `<svg viewBox="0 0 ${size} ${size}" role="img" aria-label="calories eaten versus burned">
    ${ring(rO, CO, fO, "var(--c-orange)")}
    ${ring(rI, CI, fI, "var(--c-orange-deep)")}
    <text x="${c}" y="${c - 6}" text-anchor="middle" fill="var(--ink)" font-size="30" font-weight="800" font-family="Nunito, sans-serif">${commafy(Math.abs(net))}</text>
    <text x="${c}" y="${c + 14}" text-anchor="middle" fill="${netColor}" font-size="12" font-weight="700" font-family="'Open Sans', sans-serif">kcal ${netLabel}</text>
  </svg>`;
}

/* --------------------------- science dropdown ------------------------- */
// Reusable: drop a <ScienceNote topic="fatigue" /> anywhere a recommendation shows.
function ScienceNote({ topic }) {
  const [open, setOpen] = useState(false);
  const s = SCIENCE[topic];
  if (!s) return null;
  return html`
    <div class="science">
      <button class="science-btn" aria-expanded=${open} onClick=${() => setOpen((o) => !o)}>
        <span class="flask">🔬</span> The science <span class="chev">›</span>
      </button>
      ${open && html`
        <div class="science-body">
          <p class="finding">${s.finding}</p>
          <p class="cite">${s.cite}</p>
          <div class="todo"><span>✅</span><span><b>Do this:</b> ${s.todo}</span></div>
        </div>`}
    </div>`;
}

/* --------------------------- evidence scales -------------------------- */
function evidenceScaleSVG(sig) {
  if (typeof sig.value === "boolean" || typeof sig.threshold === "boolean") return null;
  const v = Number(sig.value), t = Number(sig.threshold);
  if (!Number.isFinite(v) || !Number.isFinite(t)) return null;
  const col = sigColor(sig.name);
  const W = 480, H = 22, ax0 = 2, ax1 = 478, midY = 11;
  const tX = ax0 + 0.26 * (ax1 - ax0);
  const denom = DENOM[sig.name] || Math.abs(t) || 1;
  const sev = Math.max(0.06, Math.min(1, Math.abs(v - t) / denom));
  const vX = tX + sev * (ax1 - tX - 6);
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="severity">
    <line x1="${ax0}" y1="${midY}" x2="${ax1}" y2="${midY}" style="stroke: var(--rule)" stroke-width="2" stroke-linecap="round"/>
    <rect x="${tX.toFixed(1)}" y="7" width="${(vX - tX).toFixed(1)}" height="8" rx="4" style="fill:${col}"/>
    <line x1="${tX.toFixed(1)}" y1="3" x2="${tX.toFixed(1)}" y2="19" style="stroke:${col}" stroke-width="1.5"/>
    <circle cx="${vX.toFixed(1)}" cy="${midY}" r="5" style="fill:${col}; stroke: var(--surface)" stroke-width="2"/>
  </svg>`;
}

function EvidenceItem({ sig }) {
  const svg = evidenceScaleSVG(sig);
  const q = SIG_QUALIFIER[sig.name];
  if (!svg) {
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

/* ---------------------- diagnosis card (simplified) ------------------- */
function DiagnosisCard({ report }) {
  const [details, setDetails] = useState(false);
  const p = report.plateau;
  const top = report.causes[0];
  const rest = report.causes.slice(1);
  const fired = top ? top.signals.filter((s) => s.triggered) : [];
  const weeks = Math.max(1, Math.round(p.length_weeks));
  const cid = top && top.id;
  const accent = (cid && CAUSE_COLOR[cid]) || "var(--c-red)";
  const action = (cid && CAUSE_ACTION[cid]) || "shake it up";
  const emoji = (cid && CAUSE_EMOJI[cid]) || "📈";
  const badge = report.exercise.name.trim().charAt(0).toUpperCase();
  const chart = healthChartSVG(p.series.map((s) => s.est_1rm), { color: "#F20544", decimals: 0 });

  return html`
    <div class="dxcard" style=${{ "--dx-accent": accent }}>
      <div class="dx-top">
        <div class="dx-badge" style=${{ background: accent }}>${badge}</div>
        <div class="dx-head">
          <div class="dx-kicker">${report.exercise.muscle_group} · stuck ${weeks} week${weeks === 1 ? "" : "s"}</div>
          <h2 class="dx-line">${report.exercise.name}: <span class="action">${action}</span></h2>
          ${top && html`<span class="dx-conf"><span class="dot"></span>${CONF_WORD[top.confidence] || "Possible"} · ${top.label.toLowerCase()}</span>`}
        </div>
      </div>

      <div class="dx-chart hchart" dangerouslySetInnerHTML=${{ __html: chart }}></div>

      ${top && html`
        <div class="dx-fix"><span class="fx">${emoji}</span><p><${GlossText} text=${top.fix} /></p></div>
        <${ScienceNote} topic=${cid} />`}

      <div class="dx-actions">
        <button class="disclose" aria-expanded=${details} onClick=${() => setDetails((d) => !d)}>
          <span class="chev">›</span> ${details ? "Hide the evidence" : "See the evidence"}
        </button>
        <span class="lbl">${p.length_sessions} sessions · no new high · ~${p.frequency_per_week}×/wk</span>
      </div>

      ${details && html`
        <div>
          <div class="ev-axis">On target ← · → over the line — the colored bar shows how far past.</div>
          <div class="ev-grid">
            ${fired.map((s, i) => html`<${EvidenceItem} key=${i} sig=${s} />`)}
          </div>
          ${rest.length > 0 && html`
            <p class="also">Also possible: <b>${rest.map((c) => CAUSE_SHORT[c.id] || c.label.toLowerCase()).join(", ")}</b>.</p>`}
        </div>`}
    </div>`;
}

/* ---------------------- demo health summary (overview) ---------------- */
function HealthSummary({ summary }) {
  if (!summary) return null;
  const sleep = summary.sleep || [];
  const cals = summary.calories || {};
  const avgSleep = sleep.length ? round(sleep.reduce((a, s) => a + s.hours, 0) / sleep.length, 1) : null;
  const sleepChart = healthChartSVG(sleep.map((s) => s.hours), { color: "#03A6A6", unit: "h", decimals: 1, height: 132 });
  const eaten = cals.eaten || 0, burned = cals.burned || 0;
  const ring = calorieRingSVG(eaten, burned);
  return html`
    <div class="health-grid">
      <div class="card">
        <div class="card-head">
          <span class="dot" style=${{ background: "var(--c-teal)" }}></span>
          <span class="t">Sleep</span>
          <span class="sub">last ${sleep.length} days</span>
        </div>
        ${avgSleep != null && html`<div class="big-metric">${avgSleep}<span class="unit">h avg</span></div>`}
        <div class="hchart" style=${{ marginTop: "8px" }} dangerouslySetInnerHTML=${{ __html: sleepChart }}></div>
      </div>
      <div class="card ring-card">
        <div class="card-head">
          <span class="dot" style=${{ background: "var(--c-orange)" }}></span>
          <span class="t">Calories today</span>
        </div>
        <div class="ring-wrap" dangerouslySetInnerHTML=${{ __html: ring }}></div>
        <div class="ring-legend">
          <div class="li"><span class="sw" style=${{ background: "var(--c-orange)" }}></span> Eaten <span class="v">${commafy(eaten)}</span></div>
          <div class="li"><span class="sw" style=${{ background: "var(--c-orange-deep)" }}></span> Burned <span class="v">${commafy(burned)}</span></div>
        </div>
      </div>
    </div>`;
}

/* ------------------------------ dashboard ----------------------------- */
function Dashboard({ data, summary, loading }) {
  if (loading) return html`<div class="wrap"><div class="spinner">Reading your logs…</div></div>`;
  if (!data || !data.reports.length) {
    return html`<div class="wrap"><div class="empty">
      <span class="big">No data yet.</span>
      Set up a routine and log a few workouts. A lift needs at least four sessions before it can be judged.
    </div></div>`;
  }
  const reports = data.reports;
  const plateaus = reports.filter((r) => r.plateau.enough_data && r.plateau.is_plateau);

  const themes = [...new Set(plateaus
    .map((r) => r.causes[0] && CAUSE_THEME[r.causes[0].id]).filter(Boolean))];
  const n = plateaus.length;
  let summaryLine;
  if (n === 0) {
    summaryLine = html`Every tracked lift is still <span class="accent">moving</span>.`;
  } else {
    const list = themes.length <= 1 ? (themes[0] || "a few things")
      : themes.length === 2 ? `${themes[0]} and ${themes[1]}`
      : `${themes.slice(0, -1).join(", ")}, and ${themes[themes.length - 1]}`;
    summaryLine = html`${n} lift${n > 1 ? "s" : ""} need${n > 1 ? "" : "s"} attention — it's your <span class="accent">${list}</span>.`;
  }

  return html`
    <div class="wrap">
      <p class="summary">${summaryLine}</p>
      <${HealthSummary} summary=${summary} />
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
      ${plateaus.map((r) => html`<${DiagnosisCard} key=${r.exercise.id} report=${r} />`)}
    </div>`;
}

/* --------------------------- TDEE calculator -------------------------- */
const ACTIVITY = [
  ["1.2", "Sedentary", "little or no exercise"],
  ["1.375", "Lightly active", "1–3 days/week"],
  ["1.55", "Moderately active", "3–5 days/week"],
  ["1.725", "Very active", "6–7 days/week"],
  ["1.9", "Extremely active", "hard training / physical job"],
];
function Calculator() {
  const [f, setF] = useState({ sex: "male", age: "30", height: "175", unit: "lb", weight: "", activity: "1.55" });
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const kg = f.unit === "kg" ? num(f.weight) : num(f.weight) != null ? num(f.weight) * 0.453592 : null;
  const age = num(f.age), cm = num(f.height);
  const ready = kg && age && cm;
  let bmr = null, tdee = null;
  if (ready) {
    bmr = 10 * kg + 6.25 * cm - 5 * age + (f.sex === "male" ? 5 : -161);
    tdee = bmr * parseFloat(f.activity);
  }
  const goals = tdee && [
    ["Lose fat", tdee - 500, "var(--c-teal)"],
    ["Maintain", tdee, "var(--c-orange)"],
    ["Build muscle", tdee + 400, "var(--c-red)"],
  ];
  return html`
    <div class="wrap">
      <div class="plate">
        <div class="margin"><span class="lbl">calculator</span></div>
        <div>
          <h3 class="exercise-name">Daily calorie needs</h3>
          <p class="help">Your TDEE — how many calories you burn in a day — via the Mifflin-St Jeor equation. It needs age, height and sex on top of bodyweight to be accurate.</p>
          <div class="row" style=${{ marginTop: "var(--sp-4)" }}>
            <div class="field"><label>sex</label><select value=${f.sex} onChange=${(e) => set("sex", e.target.value)}>
              <option value="male">male</option><option value="female">female</option></select></div>
            <div class="field"><label>age</label><input type="number" min="10" max="100" value=${f.age} onChange=${(e) => set("age", e.target.value)} /></div>
            <div class="field"><label>height (cm)</label><input type="number" min="120" max="230" value=${f.height} onChange=${(e) => set("height", e.target.value)} /></div>
          </div>
          <div class="row" style=${{ marginTop: "var(--sp-4)" }}>
            <div class="field" style=${{ maxWidth: "160px" }}><label>bodyweight</label><input type="number" min="0" step="0.1" placeholder=${f.unit} value=${f.weight} onChange=${(e) => set("weight", e.target.value)} /></div>
            <div class="field" style=${{ maxWidth: "110px" }}><label>unit</label><select value=${f.unit} onChange=${(e) => set("unit", e.target.value)}>
              <option value="lb">lb</option><option value="kg">kg</option></select></div>
            <div class="field"><label>activity level</label><select value=${f.activity} onChange=${(e) => set("activity", e.target.value)}>
              ${ACTIVITY.map(([v, name, d]) => html`<option key=${v} value=${v}>${name} — ${d}</option>`)}</select></div>
          </div>

          ${ready ? html`
            <div class="tdee-result">
              <div class="tdee-hero">
                <div class="k">Your TDEE</div>
                <div class="n">${commafy(tdee)}<span class="u">kcal/day</span></div>
                <div class="bmr">Resting burn (BMR): ${commafy(bmr)} kcal · ${ACTIVITY.find((a) => a[0] === f.activity)[1]}</div>
              </div>
              <div class="tdee-goals">
                ${goals.map(([name, cal, col]) => html`
                  <div class="goal-row" key=${name}>
                    <span class="bar-dot" style=${{ background: col }}></span>
                    <span class="gname">${name}</span>
                    <span class="gcal" style=${{ color: col }}>${commafy(cal)}</span>
                  </div>`)}
              </div>
            </div>
            <${ScienceNote} topic="tdee" />
          ` : html`<p class="help" style=${{ marginTop: "var(--sp-5)" }}>Enter your bodyweight to see your estimate.</p>`}
        </div>
      </div>
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
            ${templates.map((t) => html`<button type="button" class="btn ghost small" key=${t.key} onClick=${() => pickTemplate(t.key)}>${t.name} · ${t.num_days}d</button>`)}
            <button type="button" class="btn ghost small" onClick=${() => pickTemplate("custom")}>custom</button>
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
                  <div class="nm">${e.name} <span class="pg">${e.muscle_group}</span></div>
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
                <label class="chk"><input type="checkbox" checked=${b.include} onChange=${() => toggle(bi)} /> ${b.name}</label>
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
function App() {
  const [view, setView] = useState("overview");
  const [boot, setBoot] = useState({ user: null, exercises: [], has_routine: false });
  const [diag, setDiag] = useState(null);
  const [summary, setSummary] = useState(null);
  const [routine, setRoutine] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toastMsg, setToastMsg] = useState(null);

  const toast = useCallback((m) => { setToastMsg(m); setTimeout(() => setToastMsg(null), 2600); }, []);
  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [b, d, r, t, s] = await Promise.all([
        api("/api/bootstrap"), api("/api/diagnose"), api("/api/routine"),
        api("/api/templates"), api("/api/summary"),
      ]);
      setBoot(b); setDiag(d); setRoutine(r); setTemplates(t); setSummary(s);
    } catch (err) { toast("Load error: " + err.message); } finally { setLoading(false); }
  }, [toast]);
  useEffect(() => { loadAll(); }, [loadAll]);
  const reload = useCallback(() => { loadAll(); }, [loadAll]);
  const afterSave = useCallback(() => { loadAll(); setView("overview"); }, [loadAll]);

  const tabs = [["overview", "Overview"], ["routine", "Routine"], ["log", "Log"],
    ["checkin", "Check-in"], ["calculator", "Calculator"]];

  return html`
    <div>
      <header class="masthead">
        <div class="masthead-in">
          <a class="wordmark" href="/" onClick=${goHome}>Plateau<span class="mid">·</span><span class="dx">Dx</span></a>
          <span class="who">${boot.user ? `${boot.user.display_name} · ${boot.user.goal}` : ""}</span>
          <nav class="tabs">
            ${tabs.map(([id, label]) => html`<button key=${id} class=${view === id ? "active" : ""} onClick=${() => setView(id)}>${label}</button>`)}
          </nav>
        </div>
      </header>

      <main>
        ${view === "overview" && html`<${Dashboard} data=${diag} summary=${summary} loading=${loading} />`}
        ${view === "routine" && html`<${RoutineSetup} routine=${routine} templates=${templates} onSaved=${reload} toast=${toast} />`}
        ${view === "log" && html`<${LogWorkout} routine=${routine} exercises=${boot.exercises} onSaved=${afterSave} toast=${toast} />`}
        ${view === "checkin" && html`<${DailyCheckin} onSaved=${afterSave} toast=${toast} />`}
        ${view === "calculator" && html`<${Calculator} />`}
      </main>

      ${toastMsg && html`<div class="toast">${toastMsg}</div>`}
    </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
