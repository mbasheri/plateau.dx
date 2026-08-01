# Deploying Plateau·Dx — one unified Vercel project

Everything (static frontend **and** the API) now lives on a single Vercel
domain. No Render, no CORS, no `PLATEAU_API_BASE`. The database is Postgres
(Neon, via Vercel), and the API runs as **one serverless function** hosting the
existing FastAPI app.

## Architecture at a glance

```
Browser ──► Vercel
             ├─ /                → public/index.html   (landing, auto-served)
             ├─ /app             → public/app.html     (dashboard SPA)
             ├─ /static/*        → public/*  (styles.css, app.js, vendor/)
             └─ /api/*           → api/index.py  →  FastAPI app  ──► Neon Postgres
```

- The static frontend lives in **`public/`** — the directory Vercel serves at the
  root automatically, independent of framework preset or output directory. The
  landing page is `public/index.html` (so `/` just works); the dashboard shell is
  `public/app.html`. Assets are referenced as `/static/*` and a rewrite maps that
  to `public/*`.
- `engine/` (the pure rules engine) is **untouched** by this migration.
- `server/main.py` is the API only; `api/index.py` exposes it to Vercel.
- SQLite → Postgres: `server/db.py` (schema + psycopg connection), with
  `repository.py`/`seed.py` adapted (RETURNING ids, `ILIKE`, `now()`).
- The frontend calls **relative** `/api/*` paths — same origin, so no config layer.

---

## Required environment variable

| Variable | What | Where |
|---|---|---|
| `DATABASE_URL` | Postgres connection string (**use the pooled URL**) | Vercel project → Settings → Environment Variables |

`server/db.py` also accepts `POSTGRES_URL`, which Vercel's Neon integration sets
automatically — so if you add the database through Vercel's Storage tab, you may
not need to set anything by hand.

---

## Step 1 — Create the Postgres database (Neon via Vercel)

1. Vercel Dashboard → your project → **Storage** → **Create Database** →
   **Postgres (Neon)** → follow the prompts.
2. Vercel auto-injects `POSTGRES_URL` / `DATABASE_URL` into the project's env.
3. Grab the **pooled** connection string (Neon shows a `-pooler` host) for
   serverless use.

## Step 2 — Create the schema and seed (one-off)

Serverless functions have no startup hook, so seeding is a script you run once
against the database (idempotent — safe to re-run):

```bash
DATABASE_URL="postgres://…-pooler…/neondb?sslmode=require" python -m server.seed
```

This creates all 13 tables and loads the demo athlete (anchored to *today*), so
the dashboard shows real data instead of "No data yet".

## Step 3 — Vercel project settings (important — this is what broke it before)

In the Vercel project → **Settings → Build & Deployment**:

- **Framework Preset: `Other`.** (A wrong preset makes Vercel look for a build
  output that doesn't exist and serve nothing → root `404 NOT_FOUND`.)
- **Root Directory: the repo root** (was `web` in the old split — change it back,
  empty/`./`). Vercel then reads the root `vercel.json`, serves `public/` at the
  root, and builds `api/index.py` as a Python function.
- **Build Command: empty. Output Directory: empty.** There's no build step;
  `public/` is served automatically. Do **not** set Output Directory to `web` or
  `public` — leave it blank.
- `requirements.txt` (repo root) is installed for the function automatically.

## Step 4 — Deploy

Push to the connected branch (or `vercel --prod`). Vercel serves the static
frontend from the edge and routes `/api/*` to the function.

---

## Local development (full stack)

`server/local.py` wraps the API with the static files so one command mirrors the
Vercel routing. It needs a Postgres — a free Neon **dev branch** works well:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt

export DATABASE_URL="postgres://…/neondb?sslmode=require"
./.venv/bin/python -m server.seed                              # once
./.venv/bin/python -m uvicorn server.local:app --port 8000 --reload
# open http://localhost:8000
```

To test the API exactly as it runs on Vercel (functions + static together), you
can also use `vercel dev` from the repo root.

---

## Testing before you deploy

**Engine (no DB):**
```bash
./.venv/bin/python -m pytest        # 21 tests, engine only — unaffected by the migration
```

**API against a throwaway Postgres (no external DB needed):**
```bash
./.venv/bin/python -m pip install pgserver httpx
./.venv/bin/python scripts/e2e_pg.py    # boots Postgres, seeds, hits every endpoint
```
(There's a ready-made version of this in the repo's test notes; it validates all
16 routes incl. the write paths.)

---

## End-to-end verification once deployed

1. Visit `https://<project>.vercel.app/` → the marketing landing page loads.
2. Click **See the demo** → `/app` → **Overview** shows the summary line, the
   teal sleep chart, the calorie ring, and three diagnosis cards (Bench Press →
   recover more, Overhead Press → push harder, Barbell Row → switch it up) —
   **not** "No data yet".
3. **Routine** → the Upper/Lower plan renders. **Log** → the next day is
   pre-filled. **Check-in** → save one; it succeeds. **Calculator** → enter
   bodyweight → a TDEE number appears.
4. If Overview says "No data yet", the seed step (Step 2) hasn't run against the
   database Vercel is using — re-run it with that `DATABASE_URL`.

### Troubleshooting
- **500s on `/api/*`**: check `DATABASE_URL` is set and is the **pooled** URL; view
  the function logs in Vercel.
- **`/` shows the dashboard instead of the landing page**: confirm Root Directory
  is the repo root and the root `vercel.json` is being used.
- **`ModuleNotFoundError: server`** in the function: ensure `server/` and
  `engine/` are committed at the repo root (they're imported by `api/index.py`).
