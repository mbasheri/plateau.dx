/* Runtime config for the frontend.
 *
 * PLATEAU_API_BASE is the origin of the backend API.
 *   - Local dev / all-on-Render (same-origin): leave it "" — the app calls /api/* on its own host.
 *   - Split hosting (frontend on Vercel, backend on Render): set it to the Render URL,
 *     e.g. "https://plateau-dx.onrender.com" (no trailing slash).
 *
 * On Vercel this file is what you edit per environment; nothing else needs to change.
 */
window.PLATEAU_API_BASE = "";
