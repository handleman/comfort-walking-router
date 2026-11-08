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
- Decisions: `docs/architecture/` (ADRs 001–011)

## Specs
| Spec | State | What |
| --- | --- | --- |
| `001-example-app` | T1/T2/T4/T5 done; T3 + T7–T10 queued (comfort scoring) | MVP: scored route + explanation, SQLite cache |
| `004-weather-sun` | spec→plan→tasks done | Open-Meteo preference + override |
| `005-saved-routes` | spec→plan→tasks done | No-accounts Postgres routes + prefs (ADR-007) |
| `006-comfort-plus` | spec→plan→tasks done | Lighting + traffic toggles |
| `007-live-position` | spec drafted | Walk-mode marker, drift warning, no auto-reroute |
| `008-mapbox-routing` | spec drafted | OSRM interim → Mapbox behind interface |
| `009-swarm-harness` | harness implemented, pilot running | CrewAI swarm + parallel Textual dashboard |
| `010-e2e-playwright` | spec drafted | Chromium E2E for all user scenarios |
| `011-dev-run` | done (2026-11-08) | `make dev` one-command startup + contract alignment |
| `012-dark-factory-harness` | done (2026-11-08) | Dark-factory hardening: truthful green, sandbox, merge queue, observability |

Each spec: `spec.md` → `plan.md` → `tasks.md` (`contracts/` when needed).

## Quickstart
1. Read `docs/mission.md` → `docs/roadmap.md` → the spec you care about.
2. Secrets: copy `.env.example` → `.env` (gitignored, ADR-006). Never commit keys.
3. App: `make dev` → UI at http://localhost:5173, API docs at http://localhost:8000/docs. First run creates `.venv` and installs frontend deps; `make dev-setup` pre-installs only.
4. Swarm: `make swarm-up` (pilot in background + dashboard attached), `make swarm-dash` (attach to current pilot), `make swarm-test` (unit tests). Pilot writes `swarm/runs/<ts>-<pid>-<rand>/run.json` (must show $0). Full usage: `swarm/README.md`.

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

Last verified 2026-11-08: 4 app tests + 149 harness tests pass, ruff/mypy/svelte-check clean, Vite build OK, and a live `POST /route` (Marienplatz → Viktualienmarkt, 2.04 km) rendered in headless Chrome with no JS errors.

The app venv (`.venv`) and the swarm venv (`swarm/.venv`) are separate; do not mix them.

## CrewAI swarm (learning goal 2)

The swarm implements unchecked tasks from `specs/NNN-*/tasks.md`, one task at a time:
Planner → Coder → QA → **truthful green** (gates + reviewer `PASS` + non-empty run delta + commit/push)
→ next task/spec. Full details: `swarm/README.md`.

```bash
make swarm-up        # start/resume in background + attach the dashboard
make swarm-dash      # attach to a running pilot
make swarm-run       # foreground pilot (no args = resume from last checkpoint)
make swarm-local     # all-local Ollama variant (no cloud keys)
make swarm-test      # harness unit tests (no LLM, no network)
make swarm-preflight # check models/keys/Ollama/venvs/gates before running
make swarm-stop      # stop the running pilot
make swarm-approve   # release an awaiting_approval hold (defaults to the last checkpoint task)
```

Every task writes `swarm/runs/<ts>-<pid>-<rand>/run.json` (status, gate exit codes, changed files,
reviewer verdict, approval/commit/push, tokens/cost/duration — free tiers show `$0`).
The dashboard (`make swarm-dash`) shows the queue with per-task outcomes, models/fallback,
budget gauges, gate exit codes, recent runs, and live agent panes (ADR-011).
Green runs commit on `swarm/<spec>-<task>`, push, `--no-ff` merge into the base branch, then push
(conflicts stop with `merge_failed`; `SWARM_MERGE_MODE=direct` opts out).
`make swarm-sandbox` runs the pilot in Docker with the repo as the only writable mount
(plus a read-only `/dev/null` over `.env`); on macOS use `colima start --cpu 4 --memory 8 --disk 60`.
`commit_failed`/`push_failed` are not green.
Per-run budgets (`SWARM_MAX_TOKENS`/`SWARM_MAX_COST_USD`/`SWARM_MAX_RUNTIME_SECONDS`) stop a
runaway loop with `budget_exhausted`; rate limits retry with backoff and fallback models.
Use `./swarm/run.sh 001 T3 --no-commit` to opt out of committing.

### Adding a spec so the swarm picks it up

1. Create `specs/NNN-name/` with the usual `spec.md` (why, scope, acceptance criteria),
   `plan.md` (approach, steps, risks), and `tasks.md` (start from `.specify/templates/`).
2. Write each task as an **unchecked one-line checkbox** in execution order:

   ```markdown
   - [ ] T1 (AC-1): Add the endpoint in `app/main.py` and its test in `tests/test_api.py`.
   - [ ] T2 (AC-2): Render the result in `frontend/src/App.svelte`.
   ```

   The parser only reads lines matching `- [ ] T<n> (AC-…): <brief>`; `[x]` tasks are skipped.
   Use `T1`, `T2`, … (no `T1a`), one line per task. Indented notes below the line are fine, but the
   brief on the line is what the planner passes to the coder.
3. Keep a task coder-sized: one behavior/file, 4–8 planner micro-steps, verifiable by the gates
   (`pytest`, `ruff check .`, `mypy app tests`, plus `npm test` once the frontend has a test script).
   Put exact paths and AC refs in the brief.
4. Queue order is `specs/` directory order (`001-…`, `004-…`, …). Specs without `tasks.md` and
   the harness specs `009-swarm-harness`/`012-dark-factory-harness` are skipped; a spec whose
   tasks are all `[x]` is treated as done.
5. If the task must touch paths outside the default coder scope (`app/`, `frontend/`, `tests/`,
   `contracts/`, `requirements*.txt`, `pyproject.toml`, `.gitignore`), widen it explicitly:

   ```bash
   SWARM_SCOPE=app/,frontend/,tests/,scripts/ make swarm-up
   ```

   The coder can never edit `swarm/`, `specs/`, `docs/`, or `.env*`.
6. Start it explicitly the first time (`make swarm-run SPEC=012 TASK=T1`) or let `make swarm-up`
   resume from run history. **The swarm does not edit spec files**, so mark the task `[x]` yourself
   after a green run is verified. If you changed a spec after a plan was cached, force a fresh plan:

   ```bash
   ./swarm/run.sh 012 T1 --replan
   ```

## Status
- App: MVP flow runs end-to-end (`POST /route` → geocode → OSRM → SQLite cache → Leaflet route + explanation). Comfort score is neutral until `001-T3` + T7–T10 wire Overpass/scoring; the UI states that explicitly.
- Swarm harness: implemented (`swarm/`, `Makefile` targets), 39 unit tests green. See `changelog.md` for history.
