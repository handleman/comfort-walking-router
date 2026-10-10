# Tech Stack (proposed — no manifests yet, commands unverified)

- Language: Python (version TBD at first spec; target 3.12+).
- Backend: FastAPI (serves scoring API + static map page).
- Frontend: Svelte + TypeScript for business logic (with Leaflet for map rendering) served as static build output by FastAPI. Svelte build step required (Vite).
- Route geometry: OSRM demo server, walking (MVP interim, keyless). Post-MVP: Mapbox Directions API walking (free tier, `MAPBOX_TOKEN` env, backend-only) in `008-mapbox-routing`. No self-hosting (product decision).
- Comfort data: OpenStreetMap via Overpass API (no keys). OSM tags for parks/trees/paths/roads.
- Storage: stateless first, SQLite cache for OSM responses/scores. Postgres later for saved routes/prefs.
- Test: pytest. Lint: ruff. Types: mypy.

## Swarm harness (009, learning goal #2 — implemented, pilot pending)
- Orchestration: CrewAI 1.15.27 (Flows + sequential Planner→Coder→Reviewer, `crewai[litellm]` + `crewai-tools`), Python 3.12 venv (`swarm/.venv`; system 3.14 unsupported by CrewAI).
- Models (free-first, prefix-routed in `swarm/llms.py`): `ollama/*` → local Ollama, `zen/*` → OpenCode Zen (`custom_openai` gateway), else OpenRouter. Working config: planner `openrouter/nvidia/nemotron-3-super-120b-a12b:free`, reviewer `zen/space-bunny-free`, coder local `qwen3.5:9b` (+`extra_body={"think": False}`, required — Qwen thinking blocks break LiteLLM tool parsing). Paid hard-blocked unless `SWARM_ALLOW_PAID=1`.
- Known limits (2026-10-10): OpenRouter `:free` shared pool 429s under agentic-loop load (~20–50 calls/pilot); Zen free model endpoints differ per model (`/chat/completions` vs `/responses` — only the former wired).
- Dashboard: parallel Textual TUI (per-agent panes, task list, approve/retry keys) + `--tail` attach to any run + `swarm/runs/<ts>/{run.json,events.jsonl}` trace. No web dashboard in v1.
- Commands: `make swarm-run` / `make swarm-dash` / `make swarm-up` / `make swarm-test` (`swarm/{run,dash,up}.sh` underneath; `runs/latest` pointer).
- Secrets: `.env` (gitignored) — `OPENROUTER_API_KEY`, `OPENCODE_API_KEY`, `OLLAMA_BASE_URL`, `SWARM_{PLANNER,REVIEWER,CODER}_MODEL`; see ADR-006.

## Proposed commands (confirm when manifests land)
- Backend install: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` (or `pip install -e .[dev]` if pyproject).
- Frontend install/build: `npm install` + `npm run build` in `frontend/` (Vite/Svelte, manifest TBD).
- Dev: `uvicorn app.main:app --reload` (entrypoint TBD) + `npm run dev` in `frontend/` for Svelte HMR.
- Test all: `pytest`. Single test: `pytest tests/test_<name>.py -v` (or `pytest tests/test_<name>.py::test_<id> -v`).
- Lint: `ruff check .`. Types: `mypy .` (backend) + `npm run check` / `tsc --noEmit` in `frontend/` (Svelte + TS).

> Do not treat above as verified until `pyproject.toml` / `requirements.txt` + `app/` + `frontend/package.json` exist. Update here + `AGENTS.md` then.
