# Deploying Plateau·Dx (frontend → Vercel, backend → Render)

## Why this split (the important bit)

The backend is a **stateful, long-running FastAPI process backed by SQLite**, and
it **seeds/migrates on startup** via a lifespan hook. That does not port to
Vercel's serverless model directly: serverless functions have an ephemeral
filesystem (SQLite writes wouldn't persist) and no startup lifecycle to seed on.
The *engine* (`engine/`) is pure Python and would port fine — it's the
**persistence layer** that doesn't.

So we run the **backend on Render** (SQLite + FastAPI unchanged) and put only the
**static frontend on Vercel**, pointing it at the Render API. No database
migration, no rewrite.

> The whole app also still runs as a single unit on Render (FastAPI serves the
> frontend too) or locally via `./run.sh` — the Vercel split is additive.

---

## Backend on Render (already set up)

The FastAPI app serves both `/api/*` and the static frontend. For the split, one
thing matters: allow the Vercel origin through CORS.

- Start command: `python -m uvicorn server.main:app --host 0.0.0.0 --port $PORT`
- Env var: `CORS_ORIGINS=https://<your-app>.vercel.app`
  (comma-separate multiple origins; defaults to `*` if unset).

Note the backend's public URL, e.g. `https://plateau-dx.onrender.com`.

## Frontend on Vercel

1. **Point the frontend at the backend.** Edit [`web/config.js`](web/config.js):

   ```js
   window.PLATEAU_API_BASE = "https://plateau-dx.onrender.com"; // your Render URL, no trailing slash
   ```

   (Leave it `""` for local dev / running everything on Render — then it's same-origin.)

2. **Create the Vercel project** from this repo and set **Root Directory = `web`**.
   There's no build step (vanilla React via `htm`), so:
   - Framework Preset: **Other**
   - Build Command: *(none)*
   - Output Directory: *(none — static)*

3. [`web/vercel.json`](web/vercel.json) already handles routing:
   - `/`            → `landing.html` (marketing home)
   - `/app`         → `index.html` (dashboard SPA)
   - `/static/*`    → the assets (styles, `app.js`, `config.js`, `vendor/`, `fonts/`)

That's it. The marketing page and dashboard are served from Vercel's edge; every
`/api/*` call goes to Render.

## Fonts

Nunito (wordmark) and Open Sans (everything else) load from Google Fonts via
`<link>` in both HTML files — nothing to vendor. The old self-hosted `web/fonts/`
woff2 files are no longer referenced and can be deleted if you want a smaller repo.
