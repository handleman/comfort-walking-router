# 011 Dev Run — Spec (one-command startup)

## What / Why
One command boots the whole app for local development, so any human (or pilot) can run
what the swarm builds. Before this spec nothing started cleanly: no entry point existed, the
frontend scaffold was incomplete, and the UI drifted from the contract (App posted to
`/route` but the backend served GET).

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
- [x] AC-1: Clean checkout (+ prereqs) → `make dev` serves backend :8000 and frontend :5173; Ctrl-C stops both.
- [x] AC-2: `npm run dev` and `npm run build` work in `frontend/` (scaffold complete, deps pinned).
- [x] AC-3: UI ↔ backend agree on `POST /route` matching `contracts/route.json`; no GET/POST drift.
- [x] AC-4: Browser smoke: UI loads, Leaflet map renders, one search submits with no console errors.
- [x] AC-5: `AGENTS.md` lists the exact dev commands; `pytest`/`ruff`/`mypy` stay green.

## Status (2026-11-08)
- Completed. T1 was already green (commit `f0b17aa`); T2–T4 were finished in this pass.
- `make dev` bootstraps `.venv` (Python 3.12, `requirements.txt`) + `frontend/node_modules` on
  first run, then runs uvicorn reload + Vite. Verified SIGINT stops both listeners.
- Contract: `POST /route` implemented with the request schema in `contracts/route.json`
  (`$defs.RouteRequest`); the response gained additive `geometry` (GeoJSON LineString),
  `distance_m`, `duration_s` per ADR-005. Errors use the `{ code, message }` envelope.
- Two latent bugs fixed while aligning: OSRM geometry was double-wrapped (invalid LineString)
  and `preference` was sent to OSRM as an invalid `annotations` value (every preference request
  returned 504). Upstream calls now have timeouts + a User-Agent.
- Verification: `make test` (4 passed), `make lint`, `make typecheck`, `make swarm-test`
  (39 passed), `npm run check`, `npm run build`, headless Chrome search → route drawn,
  explanation shown, no JS exceptions.
- Still open outside this spec: `001-T3` / AC-2 (real shade/sun/quiet scoring) — the API
  currently returns a neutral `comfort_score=50` and says so in the explanation.
