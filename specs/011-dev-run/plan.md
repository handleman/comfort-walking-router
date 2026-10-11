# 011 Dev Run — Plan

## Approach
Make-based entry points (repo convention is `make swarm-*`): `dev-backend` runs
`swarm/.venv/bin/python -m uvicorn app.main:app --reload --port 8000` (venv already has
FastAPI + uvicorn); `dev-frontend` runs `npm run dev` in `frontend/`; `dev` runs both with
a shared Ctrl-C trap. Frontend talks to the backend via the vite dev proxy (`/route` →
`:8000`) so the App's relative fetch works unchanged in dev. Contract (`contracts/route.json`,
ADR-005, `POST /route`) is the source of truth for the GET/POST alignment — change whichever
side is smaller. Reference spec AC-1..AC-5.

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

## Risks / Open Questions
- `npm install` weight/network on first boot — documented prereq, `node_modules/` stays gitignored.
- Port conflicts (8000/5173 busy) — fail loud with the conflicting hint; no auto-pick (deterministic URLs for E2E later).
- Backend route-method change touches T2/T4 code — keep to the decorator + request parsing, no logic changes.
- Depends on 001 T5 (App.svelte exists); runs after 010 by directory order, or standalone via `./swarm/run.sh 011 T1`.
