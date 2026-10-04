# Tech Stack (proposed — no manifests yet, commands unverified)

- Language: Python (version TBD at first spec; target 3.12+).
- Backend: FastAPI (serves scoring API + static map page).
- Frontend: Svelte + TypeScript for business logic (with Leaflet for map rendering) served as static build output by FastAPI. Svelte build step required (Vite).
- Route geometry: OSRM demo server, walking (MVP interim, keyless). Post-MVP: Mapbox Directions API walking (free tier, `MAPBOX_TOKEN` env, backend-only) in `008-mapbox-routing`. No self-hosting (product decision).
- Comfort data: OpenStreetMap via Overpass API (no keys). OSM tags for parks/trees/paths/roads.
- Storage: stateless first, SQLite cache for OSM responses/scores. Postgres later for saved routes/prefs.
- Test: pytest. Lint: ruff. Types: mypy.

## Proposed commands (confirm when manifests land)
- Backend install: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` (or `pip install -e .[dev]` if pyproject).
- Frontend install/build: `npm install` + `npm run build` in `frontend/` (Vite/Svelte, manifest TBD).
- Dev: `uvicorn app.main:app --reload` (entrypoint TBD) + `npm run dev` in `frontend/` for Svelte HMR.
- Test all: `pytest`. Single test: `pytest tests/test_<name>.py -v` (or `pytest tests/test_<name>.py::test_<id> -v`).
- Lint: `ruff check .`. Types: `mypy .` (backend) + `npm run check` / `tsc --noEmit` in `frontend/` (Svelte + TS).

> Do not treat above as verified until `pyproject.toml` / `requirements.txt` + `app/` + `frontend/package.json` exist. Update here + `AGENTS.md` then.
