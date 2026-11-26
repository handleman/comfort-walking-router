# Swarm (dark factory) learning project in a spec-driven way

Greenfield learning repo. Two goals, one product:

1. **Spec-driven development** — spec → plan → tasks → implement, small verifiable slices.
2. **Swarming agents / agentic autonomous loops** — the published [**handleman-hq**](https://github.com/handleman/handleman-hq) harness (CrewAI, provider-agnostic, local Ollama supported) implements the specs task-by-task. This repo consumes the package; it no longer vendors it.

Product under both loops: comfort-first walking router ("Google Maps for walks") — start/end → comfort-scored route + why-explanation (shade + sun + quiet from OSM).

## Entry points
- Product + goals: `docs/mission.md`
- Stack: `docs/tech-stack.md` — Python + FastAPI + Svelte + TypeScript + Leaflet, OSM/Overpass, SQLite first; swarm: CrewAI + Textual + Ollama + OpenRouter + Zen.
- Order of work: `docs/roadmap.md`
- Rules: `.specify/memory/constitution.md`, `AGENTS.md`
- Decisions: `docs/architecture/` (ADRs 001–013)
- Harness: [`handleman-hq`](https://github.com/handleman/handleman-hq) — installed in `harness/.venv`, configured by `swarm.yaml`

## Specs
| Spec | State | What |
| --- | --- | --- |
| `001-example-app` | done (T1–T11); live demo gate open | Scored route + explanation, SQLite cache |
| `004-weather-sun` | done (T1–T5) | Open-Meteo auto preference + manual override |
| `005-saved-routes` | code done; live Postgres gate open | No-accounts Postgres routes + prefs (ADR-007) |
| `006-comfort-plus` | done (T1–T5) | Lighting + traffic toggles, regression matrix |
| `007-live-position` | T1–T9 done; T10 open (mount walk mode) | Walk-mode marker, drift warning, arrival, no auto-reroute |
| `008-mapbox-routing` | done (T1–T4); needs a real token to demo | OSRM interim → Mapbox behind the provider interface |
| `009-swarm-harness` | done | CrewAI swarm + parallel Textual dashboard |
| `010-e2e-playwright` | 4 passed / 3 skipped / 3 failed 2026-11-15 | Chromium E2E for all user scenarios; the failures are 007-T10's unmounted walk mode |
| `011-dev-run` | done (2026-11-08) | `make dev` one-command startup + contract alignment |
| `012-dark-factory-harness` | done (2026-11-08) | Truthful green, sandbox, merge queue, observability |
| `013-dark-factory-phase-2` | done (2026-11-08) | Done ledger, approval-resume commit, crash checkpoints |
| `014-walk-guidance-ux` | done (T1–T11) | Geolocation, autocomplete, map picking, walker glyph, arrival |
| `020`–`025` | done | Efficiency bench, fix loop, lean loop, parallel factory, earned autonomy, durable journal |
| `026-run-guards` | done (T1–T12) | Deterministic stops: delta, fail-closed judges, corrections, quota, cost, e2e evidence, queue reasons, resume validity |

Each spec: `spec.md` → `plan.md` → `tasks.md` (`contracts/` when needed).

## Quickstart
1. Read `docs/mission.md` → `docs/roadmap.md` → the spec you care about.
2. Secrets: copy `.env.example` → `.env` (gitignored, ADR-006). Never commit keys.
3. App: `make dev` → UI at http://localhost:5173, API docs at http://localhost:8000/docs. First run creates `.venv` and installs frontend deps; `make dev-setup` pre-installs only.
4. Harness: `make swarm-up` (pilot in background + dashboard attached), `make swarm-dash` (attach), `make swarm-test` (install check: `hq --version` + `preflight`), `make swarm-health` (app tests + e2e). Runs land in `harness/runs/<ts>-<pid>-<rand>/run.json`. Docs: [`handleman-hq`](https://github.com/handleman/handleman-hq#readme).

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
make swarm-test    # harness install check (hq --version + preflight)
make e2e           # browser suite (build + fixture backend + playwright)
make swarm-health   # app tests + e2e; non-zero when the stand is broken
make swarm-accept   # spec acceptance pass (ARGS="--selftest --strict")
make accept-live    # live-only ACs: real Mapbox, Postgres, the Render deployment

cd frontend && npm run check && npm run build
```

Single app test:

```bash
.venv/bin/python -m pytest tests/test_route_api.py::test_route_matches_contract -v
```

Last verified 2026-11-16: **214 app tests + 724 harness tests** pass, ruff/mypy clean, Vite build OK, `make e2e` **12 passed** (fixture backend + `vite preview`).

The app venv (`.venv`) and the harness venv (`harness/.venv`) are separate; do not mix them. The harness is a dependency (`handleman-hq`), not a second copy of the source.

## Verification

| Command | Proves |
| --- | --- |
| `make test` | 218 app pytest (route contract, comfort scoring, saved-routes DB paths). |
| `make lint` | `ruff check .` — style + enabled static rules. |
| `make typecheck` | `mypy app tests` — backend type safety. |
| `make swarm-test` | 724 harness unit tests (queue, guards, prompts, ledger). |
| `make e2e` | 12 Playwright — user scenarios in a browser, against fixtures. |
| `make smoke-live` | one real Munich route through the live providers. |
| `make swarm-preflight` | models/keys/venvs/gates usable before the first LLM call. |

Runbooks: [local-postgres](docs/runbooks/local-postgres.md), [e2e-suite](docs/runbooks/e2e-suite.md),
[verification](docs/runbooks/verification.md), [deploy](docs/runbooks/deploy.md). Harness internals: [handleman-hq docs](https://github.com/handleman/handleman-hq/tree/main/docs).

**Live deployment:** https://comfort-walking-router.onrender.com/ (Render free tier, auto-redeploys on every commit to `main`).

## Geocoding (spec 014)

Address autocomplete and reverse geocoding are served by `GET /geocode?q=…` and
`GET /geocode/reverse?lat=…&lng=…`, returning the normalized `Suggestion` shape from
`contracts/geocode.json` (`id`, `label`, `lat`, `lng`, `type`, `attribution`).

**Setup (optional, backend-only):** the provider chain is free-first. With no extra config the
backend uses [Photon](https://photon.komoot.io) (OSM-based, no key). To use Mapbox Geocoding v6
instead, set `MAPBOX_TOKEN` in `.env` (copy `.env.example` → `.env`; the token is read only by the
backend, never shipped to the frontend, and is gitignored per ADR-006). No other setup is needed;
results are cached in SQLite for 5 minutes to stay well inside provider rate limits.

**Attribution / credit (required, do not remove):** geocoding results must keep their
`attribution` string visible wherever suggestions are shown. Mapbox results: "© Mapbox ©
OpenStreetMap" plus any listed data providers. Photon/OSM results: "© OpenStreetMap contributors",
with Photon/Komoot credited as the geocoder. If you display a map alongside suggestions, keep the
map's own attribution control intact (Leaflet's, plus Mapbox's when a Mapbox token is used).

### Live-only acceptance

The strict pass is hermetic (`ROUTE_FIXTURES=1`, no database), so a few ACs are
declared `live-only` in `acceptance.toml` instead of being faked there:

| Spec | AC | Needs |
| --- | --- | --- |
| 008 mapbox-routing | AC-1 | real Mapbox (the `.env` token) |
| 004 weather-sun | AC-3 | manual prefs persist (Postgres) |
| 005 saved-routes | AC-1 | save/recall/delete (Postgres) |
| 035 free-deployment | AC-1/AC-2 | https://comfort-walking-router.onrender.com/ |

Each declares a `live.toml`; `make accept-live` serves the same build with
fixtures **off** and drives it, writes `acceptance-live.md` next to
`acceptance.md`, and skips (not fails) the database specs when Postgres is down
(`make swarm-db-up` first). It is opt-in because it is network/quota dependent;
the strict gate stays deterministic.

### Design from Figma

The Figma design is being prepared. Two lanes are documented in
[docs/figma.md](docs/figma.md):

- **Operator (OpenCode):** the remote Figma MCP server in `opencode.json`
  (`https://mcp.figma.com/mcp`, OAuth via `/mcps`) plus the
  `figma-implement` skill.
- **Queue (harness):** MCP with first-run OAuth (URL → browser callback → token
  → continue) **or** REST with a personal access token; both write a committed
  design cache for `hq design sync` (factory spec 057), with deterministic
  token/region/screenshot checks. The draft product spec is
  `specs/product/041-figma-redesign/` (do not queue until the file link and
  frames are filled).

## CrewAI swarm (learning goal 2)

A measured, cloud-first swarm that implements unchecked `specs/*/tasks.md` tasks one
at a time. Each phase is a small CrewAI crew with its own model role; a Flow
(the harness flow) sequences them and owns what a model must not decide — retries,
scope, green, commit. **Green is QA's gate evidence** (exit codes recorded in the
run's `shell_log.jsonl`), never a model's prose; the verifier, self-check and
correction crews run under their own roles so their work can never count as gate
evidence. Deterministic guards stop with typed reason codes (`no_delta`,
`delta_incomplete`, `correction_reverted`, `e2e_missing`, `quota_exhausted`,
`wall_budget`, `verifier_blocked`) instead of spending a judge to find out.

```bash
make swarm-up        # start/resume in background + attach the dashboard
make swarm-run       # foreground pilot (no args = resume from last checkpoint)
make swarm-test      # harness unit tests (no LLM, no network)
make swarm-preflight # models/keys/venvs/gates before the first LLM call
```

Every task writes `harness/runs/<ts>-<pid>-<rand>/` (`run.json`, `events.jsonl`,
`shell_log.jsonl`, `progress.json`, `journal.db`, `human_log.txt`); the dashboard
(`make swarm-dash`) shows the queue, models/fallbacks, budget gauges, gates and recent
runs (ADR-011). Green runs commit on `swarm/<spec>-<task>`, push, and `--no-ff` merge
into the base branch (`merge_failed` stops a conflict); `SWARM_MERGE_MODE=direct` opts
out, `./harness/run.sh 001 T3 --no-commit` skips the commit.

**Documentation**: the harness docs live with the factory — [README](https://github.com/handleman/handleman-hq#readme),
[how it works](https://github.com/handleman/handleman-hq/blob/main/docs/how-it-works.md),
[model usage](https://github.com/handleman/handleman-hq/blob/main/docs/model-usage.md).
Start with [how-it-works](https://github.com/handleman/handleman-hq/blob/main/docs/how-it-works.md)
(roles, phase order, flow diagram, the invariant); then
[run-guards](https://github.com/handleman/handleman-hq/blob/main/docs/run-guards.md)
(the deterministic stops and their off switches),
[queue](https://github.com/handleman/handleman-hq/blob/main/docs/queue.md) and
[usage-and-budgets](https://github.com/handleman/handleman-hq/blob/main/docs/usage-and-budgets.md).

Economics: `make swarm-report` (cost per green task, tokens per role, fix rate, stops) and
`make swarm-supervise` (unattended queue with retry/backoff). Per-run budgets
(`SWARM_MAX_TOKENS`/`SWARM_MAX_COST_USD`/`SWARM_MAX_RUNTIME_SECONDS`) stop a runaway
loop with `budget_exhausted`. The container sandbox lives in the factory image
(`handleman-hq`).

## Status
- App: MVP flow runs end-to-end (`POST /route` → geocode → OSRM → SQLite cache → Leaflet route + explanation). Comfort score is neutral until `001-T3` + T7–T10 wire Overpass/scoring; the UI states that explicitly.
- Harness: the published [handleman-hq](https://github.com/handleman/handleman-hq) package (pinned `v0.6.3`) in `harness/.venv`, configured by `swarm.yaml` (including `runs_dir: harness/runs`); this repo keeps the queue, specs and run traces. See `changelog.md`.
