# Tech Stack (implemented; commands verified 2026-11-08)

- Language: Python 3.12 (root `.venv`, `requirements.txt`); Node + npm for the frontend.
- Backend: FastAPI, single entrypoint `app/main.py` (`POST /route`).
- Frontend: Svelte 4 + TypeScript business logic + Leaflet map, Vite dev server on `:5173`
  with a `/route` proxy to the backend on `:8000`. Production build: `npm run build`.
- Route geometry: OSRM demo server (car profile interim, keyless). Post-MVP: Mapbox Directions
  API walking (free tier, `MAPBOX_TOKEN` env, backend-only) in `008-mapbox-routing`. No self-hosting.
- Comfort data: OpenStreetMap via Overpass API (no keys). **Not wired yet** (`001-T3`): the
  provider is a stub and the API returns a neutral comfort score.
- Storage: SQLite cache (`cache.db`, gitignored) keyed by `(start, end, preference)`.
  Postgres later for saved routes/prefs (ADR-007).
- Test: pytest (app `tests/`, harness `swarm/tests/`). Lint: ruff. Types: mypy + svelte-check.

## Commands (verified)
- Install everything: `make dev-setup` (creates `.venv` from `requirements*.txt`, runs `npm install`).
- Dev (one command): `make dev` — bootstraps missing deps, backend `:8000` + frontend `:5173`, Ctrl-C stops both.
- One side: `make dev-backend` / `make dev-frontend`.
- App tests: `make test`. Single test: `.venv/bin/python -m pytest tests/test_route_api.py::test_route_matches_contract -v`.
- Harness tests: `make swarm-test` (`swarm/.venv`).
- Lint: `make lint` (`ruff check .`). Types: `make typecheck` (`mypy app tests`).
- Frontend checks: `cd frontend && npm run check` (svelte-check), `npm run build` (Vite).

> The app venv (`.venv`) and the swarm venv (`swarm/.venv`, CrewAI) are separate on purpose —
> do not install harness deps into the app environment or vice versa.

## Geocoding (014, AC-8/AC-9 — implemented)
- Provider chain (ADR-013): Mapbox Geocoding v6 when `MAPBOX_TOKEN` is set and non-empty
  (the repo-wide variable name, backend-only, see `app/config.py` and ADR-006), Photon
  (`photon.komoot.io`, tokenless, OpenStreetMap-based) otherwise. The choice is made per
  call, both providers are hit with `requests` and an 8-second timeout, and any transport
  or parse failure degrades to an empty suggestion list — never a 500.
- Endpoints: `GET /geocode?q=…` (forward search) and `GET /geocode/reverse?lat=…&lng=…`
  (reverse geocoding); both return `{"suggestions": [Suggestion, ...]}`.
- Normalized shape: every provider result is normalized in `app/geocoding.py` into one
  frozen dataclass — `Suggestion(id, label, lat, lng, type, attribution)` — so Mapbox v6
  and Photon payload differences never leak into the HTTP contract or the frontend.
- Cache: SQLite TTL cache in `app/geocode_cache.py` with `TTL_SECONDS = 300` (5 minutes).
  Keys are `fwd:{q}:{lat}:{lng}:{limit}` and `rev:{lat}:{lng}`; rows are upserted on write,
  deleted lazily on expired read, and served before any provider call. The database is
  overridable via `GEOCODE_CACHE_DB` (in-memory by default), the connection is shared across
  threads behind a reentrant lock, and the cache is best-effort: any SQLite error falls
  through to the provider.
- Attribution: Mapbox results carry `© Mapbox © OpenStreetMap`, Photon results
  `© OpenStreetMap contributors`; the `attribution` field travels with every suggestion and
  is displayed by the frontend. Setup (`MAPBOX_TOKEN`) and credit obligations: see README.md.

## Swarm harness (009, learning goal #2 — implemented)
- Orchestration: CrewAI 1.15.27 (Flows + sequential Planner→Coder→Reviewer, `crewai[litellm]` + `crewai-tools`), Python 3.12 venv (`swarm/.venv`; system Python 3.14+ unsupported by CrewAI).
- Models (prefix-routed in `swarm/llms.py`): `ollama/*` → local Ollama, `zen/*` → OpenCode Zen (`custom_openai` gateway; base URL stops at `/v1`), else OpenRouter. Operator profile since 2026-11-14 is **cloud-only** (`SWARM_LOCAL_FIRST=0`): planner `openrouter/deepseek/deepseek-v4.1-flash-1017`, coder `zen/glm-5.3-flash`, reviewer/verifier/senior `zen/glm-5.3-flash` (the free Nvidia tier hit its daily 1000-request quota on 2026-11-14, so those roles are paid and every one has a `zen/deepseek-v4.1-flash` fallback). The 2026-11-08 free-first pair (local coder `ollama/swarm-coder:latest` + reviewer `ollama/swarm-qa:latest`, Qwen3.5 9B, `extra_body={"think": False}` required — thinking blocks break LiteLLM tool parsing) stays available via `make swarm-local`. Paid hard-blocked unless `SWARM_ALLOW_PAID=1`; `make swarm-preflight` validates ids/keys/Ollama/gates before the first LLM call (`preflight_failed`).
- Known limits (2026-11-08): OpenRouter `:free` shared pool 429s under load (~20 req/min, 50–1000/day depending on credits); Zen free models are client-only via API key (paid `deepseek-v4.1-flash` / `glm-5.3-flash` are the cheap fallbacks); `gpt-5.4-nano` and `beam-free` are region-blocked (DE); `llama3.2:1b` emits malformed tool args.
- Dashboard: read-only Textual operator console (`swarm/tui.py`, ADR-011): spec queue with per-task outcomes, models/fallback, tokens/cost/time budget gauges, gate exit codes, recent runs, per-agent panes; live or `--tail` attach. No web dashboard in v1; per-call tracing is an optional OpenInference/OTel export (Phoenix locally).
- Commands: `make swarm-run` / `make swarm-dash` / `make swarm-up` / `make swarm-test` / `make swarm-preflight` (`swarm/{run,dash,up}.sh` underneath; `runs/latest` pointer).
- Commit path: branch-per-task + merge queue (012 T18) — commit on `swarm/<spec>-<task>`, push, `--no-ff` merge into the base branch, push base; conflicts → `merge_failed`, failed base push rolls the merge back; `SWARM_MERGE_MODE=direct` for the old path.
- Sandbox: `make swarm-sandbox` runs the pilot in Docker with the repo as the only writable mount (plus `/dev/null` over `.env`); caps dropped, host UID, no HOME/SSH by default. On macOS use Colima: `colima start --cpu 4 --memory 8 --disk 60`. Keys via `--env-file .env`; commits default off with `SWARM_SANDBOX_ALLOW_COMMIT`/`SWARM_SANDBOX_SSH` opt-ins. Verified 2026-11-08 (in-container tests, OpenRouter + host Ollama).
- Run recovery (013): done ledger from commit trailers + `swarm/runs/done.json` cache (skip green-unchecked tasks, reopen on spec/plan/task changes); held-run approval commits the verified delta; per-step `progress.json` resumes a killed run after plan/file/age validation (`SWARM_RESUME_MAX_AGE_SECONDS`).
- Observability: `run.json` carries a `usage` block (tokens, cached tokens, LLM calls, models, cost, start/finish/duration); per-run budgets (`budget_exhausted`) and quota/429 fallback with backoff. All gates run locally (`make test`, `make swarm-test`, `make lint`, `make typecheck`, frontend `npm run check/build`); no GitHub Actions workflow.
- Secrets: `.env` (gitignored) — `OPENROUTER_API_KEY`, `OPENCODE_API_KEY`, `OLLAMA_BASE_URL`, `SWARM_{PLANNER,REVIEWER,CODER,SENIOR}_MODEL`, `SWARM_ZEN_{BASE_URL,FALLBACK_MODEL}`; see ADR-006.
