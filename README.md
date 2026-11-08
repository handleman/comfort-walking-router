# spec-driven-learn

Greenfield learning repo. Two goals, one product:

1. **Spec-driven development** — spec → plan → tasks → implement, small verifiable slices.
2. **Swarming agents / agentic autonomous loops with CrewAI** — a free-first local swarm that implements the specs task-by-task (`specs/009-swarm-harness/`).

Product under both loops: comfort-first walking router ("Google Maps for walks") — start/end → comfort-scored route + why-explanation (shade + sun + quiet from OSM).

## Entry points
- Product + goals: `docs/mission.md`
- Stack: `docs/tech-stack.md` — Python + FastAPI + Svelte + TypeScript + Leaflet, OSM/Overpass, SQLite first; swarm: CrewAI + Textual + Ollama + OpenRouter + Zen.
- Order of work: `docs/roadmap.md`
- Rules: `.specify/memory/constitution.md`, `AGENTS.md`
- Decisions: `docs/architecture/` (ADRs 001–010)

## Specs
| Spec | State | What |
| --- | --- | --- |
| `001-example-app` | T1/T2/T4/T5 done; T3 (comfort scoring) open | MVP: scored route + explanation, SQLite cache |
| `004-weather-sun` | spec→plan→tasks done | Open-Meteo preference + override |
| `005-saved-routes` | spec→plan→tasks done | No-accounts Postgres routes + prefs (ADR-007) |
| `006-comfort-plus` | spec→plan→tasks done | Lighting + traffic toggles |
| `007-live-position` | spec drafted | Walk-mode marker, drift warning, no auto-reroute |
| `008-mapbox-routing` | spec drafted | OSRM interim → Mapbox behind interface |
| `009-swarm-harness` | harness implemented, pilot running | CrewAI swarm + parallel Textual dashboard |
| `010-e2e-playwright` | spec drafted | Chromium E2E for all user scenarios |
| `011-dev-run` | done (2026-11-08) | `make dev` one-command startup + contract alignment |

Each spec: `spec.md` → `plan.md` → `tasks.md` (`contracts/` when needed).

## Quickstart
1. Read `docs/mission.md` → `docs/roadmap.md` → the spec you care about.
2. Secrets: copy `.env.example` → `.env` (gitignored, ADR-006). Never commit keys.
3. App: `make dev` → UI at http://localhost:5173, API docs at http://localhost:8000/docs. First run creates `.venv` and installs frontend deps; `make dev-setup` pre-installs only.
4. Swarm: `make swarm-up` (pilot in background + dashboard attached), `make swarm-dash` (attach to current pilot), `make swarm-test` (unit tests). Pilot writes `swarm/runs/<ts>/run.json` (must show $0). Full usage: `swarm/README.md`.

## Development commands

### Start
| Command | What |
| --- | --- |
| `make dev` | One command: bootstraps `.venv` + `frontend/node_modules` on first run, serves API on `:8000` and UI on `:5173`, Ctrl-C stops both. |
| `make dev-setup` | Install Python + frontend deps only (does not start servers). |
| `make dev-backend` | Backend only: http://localhost:8000/docs |
| `make dev-frontend` | Frontend only: http://localhost:5173 (Vite proxies `/route` to `:8000`). |

### Verify
```bash
make test          # app pytest (tests/)
make lint          # ruff check .
make typecheck     # mypy app tests
make swarm-test    # harness pytest (swarm/.venv)

cd frontend && npm run check && npm run build
```

Single app test:

```bash
.venv/bin/python -m pytest tests/test_route_api.py::test_route_matches_contract -v
```

Last verified 2026-11-08: 4 app tests + 39 harness tests pass, ruff/mypy/svelte-check clean, Vite build OK, and a live `POST /route` (Marienplatz → Viktualienmarkt, 2.04 km) rendered in headless Chrome with no JS errors.

The app venv (`.venv`) and the swarm venv (`swarm/.venv`) are separate; do not mix them.

## Status
- App: MVP flow runs end-to-end (`POST /route` → geocode → OSRM → SQLite cache → Leaflet route + explanation). Comfort score is neutral until `001-T3` wires Overpass/scoring; the UI states that explicitly.
- Swarm harness: implemented (`swarm/`, `Makefile` targets), 39 unit tests green. See `changelog.md` for history.
