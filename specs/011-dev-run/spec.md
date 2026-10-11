# 011 Dev Run — Spec (one-command startup)

## What / Why
One command boots the whole app for local development, so any human (or pilot) can run
what the swarm builds. Today nothing starts cleanly: no entry point exists, the frontend
scaffold is incomplete (no `index.html`/`main.ts`, no `vite` or `leaflet` deps), and the
UI drifts from the contract (App posts to `/route` but the backend serves GET).

## Scope
- In scope:
  - `make dev` boots backend (uvicorn reload, :8000) + frontend (vite dev, :5173) with one
    command; one Ctrl-C stops both. `make dev-backend` / `make dev-frontend` run each alone.
  - Complete the frontend scaffold: `index.html`, `src/main.ts`, `vite.config.ts` (dev proxy
    `/route` → backend), missing deps (`vite`, `leaflet`), `npm run dev` serves, `npm run build` passes.
  - Contract alignment: UI and backend agree on `POST /route` per ADR-005 and
    `contracts/route.json` (fix whichever side drifts, minimal diff).
  - Boot verification: both URLs respond, UI loads with map, one search submits without
    console errors (manual smoke).
  - `AGENTS.md` updated with the exact dev commands (repo rule: stack commands recorded once real).
- Non-goals:
  - No production deploy, no Docker, no process manager (dev-only; Ctrl-C lifecycle).
  - No new product features, no UI redesign, no backend logic changes beyond the route-method alignment.
  - No committed secrets; ports fixed (8000/5173) with proxy, no env plumbing beyond existing `.env`.

## Acceptance Criteria
- [ ] AC-1: Clean checkout (+ prereqs) → `make dev` serves backend :8000 and frontend :5173; Ctrl-C stops both.
- [ ] AC-2: `npm run dev` and `npm run build` work in `frontend/` (scaffold complete, deps pinned).
- [ ] AC-3: UI ↔ backend agree on `POST /route` matching `contracts/route.json`; no GET/POST drift.
- [ ] AC-4: Browser smoke: UI loads, Leaflet map renders, one search submits with no console errors.
- [ ] AC-5: `AGENTS.md` lists the exact dev commands; `pytest`/`ruff`/`mypy` stay green.
