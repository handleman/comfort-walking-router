# 011 Dev Run — Plan

## Approach
Make-based entry points (repo convention is `make swarm-*`): `dev-backend` runs
`.venv/bin/python -m uvicorn app.main:app --reload --port 8000`; `dev-frontend` runs
`npm run dev` in `frontend/`; `dev` runs both with a shared Ctrl-C trap. Frontend talks to
the backend via the vite dev proxy (`/route` → `:8000`) so the App's relative fetch works
unchanged in dev. Contract (`contracts/route.json`, ADR-005, `POST /route`) is the source of
truth for the GET/POST alignment — change whichever side is smaller. Reference spec AC-1..AC-5.

## Steps
1. Frontend scaffold: `index.html` (mount `#app`, loads `/src/main.ts`), `src/main.ts`
(mounts `App.svelte`), `vite.config.ts` (svelte plugin + `/route` proxy → `:8000`); add
`vite` + `leaflet` deps; `npm install` clean, `npm run dev` serves, `npm run build` passes (AC-2).
2. Contract alignment: make UI fetch and backend route agree on `POST /route` with the
`contracts/route.json` shape; keep the diff to method + call site (AC-3).
3. Entry points: `make dev-backend`, `make dev-frontend`, `make dev` (both, one Ctrl-C stops
all); document ports (8000/5173) (AC-1).
4. Verify: boot both, curl backend docs/route, load UI, submit one search, no console errors;
`pytest`/`ruff`/`mypy` green; record exact commands in `AGENTS.md` (AC-4, AC-5). Note:
`AGENTS.md` is human-owned docs — the pilot drafts the command lines, a human confirms them.

## Outcome (2026-11-08)
- Deviation from step 1: app dependencies live in a root `.venv` created from
  `requirements.txt` / `requirements-dev.txt` (Python 3.12), not in `swarm/.venv`. The swarm
  venv stays CrewAI-only; two environments avoid pulling the harness into app installs.
  `make dev` auto-creates the venv and runs `npm install` when missing, so it is still one command.
- Contract was extended additively (ADR-005 allows additive changes): `geometry` (GeoJSON
  LineString), `distance_m`, `duration_s` on the response, plus `$defs.RouteRequest` and
  `$defs.Error`. The UI needs geometry + distance/time to satisfy 001 AC-1; the old schema
  had no way to render a route.
- Backend entrypoint is `app/main.py` only. The swarm-generated `app/router.py` (wrong relative
  import, `name/age` request model, fake response) was deleted; `app/__init__.py` is empty again.
- `POST /route` keeps the existing geocode → OSRM → cache flow, but wraps it in the contract
  shape and maps errors to `{ code, message }` (`404`, `422`, `502`, `504`).
- Frontend: Leaflet stylesheet imported, real map height, submit handler, loading/error states,
  start/end markers, `fitBounds`, explanation panel. `vite.config.ts` now uses the named
  `svelte` plugin export (the default import the scaffold used never loaded).
- Tests: `tests/test_route_api.py` (contract shape, cache hit, 422 enum) and
  `tests/test_osrm_provider.py` (geometry pass-through regression). Root `pytest` is scoped to
  `tests/`; the CrewAI suite stays explicit via `make swarm-test`.
- Verification results: 4 app tests passed; ruff clean; mypy clean (app + tests); svelte-check
  0 errors; `vite build` OK; `make dev` served both ports; SIGINT stopped both; headless Chrome
  search rendered the route with no JS exceptions.

## Risks / Open Questions
- `npm install` weight/network on first boot — documented prereq, `node_modules/` stays gitignored.
- Port conflicts (8000/5173 busy) — fail loud with the conflicting hint; no auto-pick (deterministic URLs for E2E later).
- Backend route-method change touches T2/T4 code — keep to the decorator + request parsing, no logic changes.
- Depends on 001 T5 (App.svelte exists); runs after 010 by directory order, or standalone via `./swarm/run.sh 011 T1`.
- Comfort scoring is still neutral (`001-T3`/AC-2); OSRM demo uses its car profile until 008 swaps in Mapbox walking.
