# 011 Dev Run — Tasks

- [ ] T1 (AC-2): Complete frontend scaffold (`index.html`, `src/main.ts`, `vite.config.ts` with `/route` proxy, add `vite` + `leaflet` deps); `npm install` clean, `npm run dev` serves, `npm run build` passes.
- [ ] T2 (AC-3): Align UI fetch + backend route on `POST /route` per `contracts/route.json` (minimal diff, method + call site only).
- [ ] T3 (AC-1): `make dev-backend` / `make dev-frontend` / `make dev` (uvicorn reload :8000 + vite :5173, one Ctrl-C stops all); document ports.
- [ ] T4 (AC-4, AC-5): Boot verify (backend docs/route respond, UI loads + map renders + one search, no console errors) + draft `AGENTS.md` dev commands for human confirm; `pytest`/`ruff`/`mypy` green.
