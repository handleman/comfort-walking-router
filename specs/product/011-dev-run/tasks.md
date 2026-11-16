# 011 Dev Run — Tasks

- [x] T1 (AC-2): Complete frontend scaffold (`index.html`, `src/main.ts`, `vite.config.ts` with `/route` proxy, add `vite` + `leaflet` deps); `npm install` clean, `npm run dev` serves, `npm run build` passes.
  - Done earlier by the swarm (commit `f0b17aa`). Re-verified 2026-11-08: `npm install`, `npm run dev`, `npm run build`, `npm run check` all pass. Follow-up fixes in T2/T3: named `svelte` plugin import, Leaflet CSS, mount cleanup.
- [x] T2 (AC-3): Align UI fetch + backend route on `POST /route` per `contracts/route.json` (minimal diff, method + call site only).
  - Done 2026-11-08. Deleted broken swarm `app/router.py`; `app/main.py` is the single entrypoint. Contract extended additively with `geometry`/`distance_m`/`duration_s` + `$defs.RouteRequest`/`$defs.Error`; UI posts `{ start, end, preference }` and renders the contract response. Regression tests cover shape, cache, 422, and OSRM geometry pass-through.
- [x] T3 (AC-1): `make dev-backend` / `make dev-frontend` / `make dev` (uvicorn reload :8000 + vite :5173, one Ctrl-C stops all); document ports.
  - Done 2026-11-08. `make dev` bootstraps `.venv` + `node_modules` on first run; SIGINT to the foreground process group stops both listeners. Ports: backend 8000, frontend 5173 (strict).
- [x] T4 (AC-4, AC-5): Boot verify (backend docs/route respond, UI loads + map renders + one search, no console errors) + draft `AGENTS.md` dev commands for human confirm; `pytest`/`ruff`/`mypy` green.
  - Done 2026-11-08. `make dev` → `GET /docs` 200, `GET /` 200, live `POST /route` 200 via the Vite proxy. Headless Chrome: map tiles render, search returns "Marienplatz, Munich → Viktualienmarkt, Munich", 2.04 km route drawn, explanation shown, no JS exceptions. `make test` 4 passed, `make lint` clean, `make typecheck` clean, `npm run check` 0 errors, `make swarm-test` 39 passed. `AGENTS.md` records the commands.
