# spec-driven-learn

Greenfield learning repo. Two goals, one product:

1. **Spec-driven development** — spec → plan → tasks → implement, small verifiable slices.
2. **Swarming agents / agentic autonomous loops with CrewAI** — a free-first local swarm that implements the specs task-by-task (`specs/009-swarm-harness/`).

Product under both loops: comfort-first walking router ("Google Maps for walks") — start/end → comfort-scored route + why-explanation (shade + sun + quiet from OSM).

## Entry points
- Product + goals: `docs/mission.md`
- Stack (proposed, unverified): `docs/tech-stack.md` — Python + FastAPI + Svelte + TypeScript + Leaflet, OSM/Overpass, SQLite first; swarm: CrewAI + Textual + Ollama + OpenRouter + Zen.
- Order of work: `docs/roadmap.md`
- Rules: `.specify/memory/constitution.md`, `AGENTS.md`
- Decisions: `docs/architecture/` (ADRs 001–010)

## Specs
| Spec | State | What |
| --- | --- | --- |
| `001-example-app` | spec→plan→tasks done | MVP: scored route + explanation, SQLite cache |
| `004-weather-sun` | spec→plan→tasks done | Open-Meteo preference + override |
| `005-saved-routes` | spec→plan→tasks done | No-accounts Postgres routes + prefs (ADR-007) |
| `006-comfort-plus` | spec→plan→tasks done | Lighting + traffic toggles |
| `007-live-position` | spec drafted | Walk-mode marker, drift warning, no auto-reroute |
| `008-mapbox-routing` | spec drafted | OSRM interim → Mapbox behind interface |
| `009-swarm-harness` | spec→plan→tasks done, not implemented | CrewAI swarm + Textual TUI; pilot = `001-T1` at $0 |

Each spec: `spec.md` → `plan.md` → `tasks.md` (`contracts/` when needed).

## Quickstart (docs-first)
1. Read `docs/mission.md` → `docs/roadmap.md` → the spec you care about.
2. Secrets: copy `.env.example` → `.env` (gitignored, ADR-006). Never commit keys. Current keys: `OPENROUTER_API_KEY`, `OPENCODE_API_KEY`, `OLLAMA_BASE_URL`, later `MAPBOX_TOKEN` (backend-only).
3. App: no manifests yet — commands in `docs/tech-stack.md` are proposed until `app/` + `frontend/package.json` land (then `pytest`, `ruff check .`, `mypy .`, `npm run check`).
4. Swarm pilot (after `swarm/` lands per 009 tasks): `python -m swarm.flow --spec 001 --task T1 --no-paid`, watch Textual TUI, check `swarm/runs/<ts>/run.json` (must show $0).

## Status
No app or swarm code yet — specs only. See `changelog.md` for history.
