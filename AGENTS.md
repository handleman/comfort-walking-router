# AGENTS.md

Learning repo for spec-driven development + swarming agents / agentic autonomous loops with CrewAI.

## State
- App MVP is runnable: FastAPI backend (`app/main.py`, `POST /route`), Svelte + Vite + Leaflet frontend (`frontend/`), SQLite cache (`cache.db`, gitignored). OSRM demo supplies interim geometry (car profile; Mapbox walking in 008). Comfort scoring is still neutral — `001-T3` (Overpass provider) is done; T7–T10 remain.
- Specs are the source of truth: work goes `spec.md` → `plan.md` → `tasks.md` under `specs/NNN-name/`; decisions in `docs/architecture/`; durable docs in `docs/`.
- SDD layout (Option 2, Spec-Kit style): constitution in `.specify/memory/constitution.md`, transient work in `specs/NNN-name/` (`contracts/` when needed). Templates in `.specify/templates/`.
- Swarm (learning goal 2, `specs/009-swarm-harness/`): pure CrewAI coders + parallel Textual dashboard, free-first prefix routing (Ollama local → OpenRouter `:free` → Zen free). Usage: `swarm/README.md`.
- Gate ownership (015): QA is the only agent that runs gates; every coder crew gets `ShellTool(allow_gates=False)` and works from QA's report (per-gate argv, exit code, failure output). The harness records each execution in `<run>/shell_log.jsonl` and derives green from those records (`qa_gate_missing` when stale/missing), so truthful green no longer needs the flow to re-run gates (`SWARM_TRUST_QA_EVIDENCE=0` restores that). Fix rounds are QA→coder→QA, max 3.
- Dark-factory hardening (`specs/012-dark-factory-harness/`, Phase 1 T11–T18 done): run-delta attribution (only this run's changes are gated/committed), tool-level scope + secret guards, argv-only shell, reviewer `PASS` required, vacancy guard on cached plans, content-hashed plan cache, commit/push coupled to green, single-run lock/PID/signals, approval holds, role-aware prompts, AC evidence + token/cost/timestamps in `run.json`, preflight, retry/backoff + model fallbacks, per-run budgets (`budget_exhausted`), listener teardown, incremental TUI tail, branch-per-task + `--no-ff` merge queue with rollback (`merge_failed`), a container sandbox (repo-only mount, `.env` masked), and an operator dashboard (ADR-011: queue outcomes, models/fallback, budget gauges, gates, recent runs). Gates run locally via `make` targets; there is no CI workflow.

## Commands (verified 2026-11-08)
- One command dev: `make dev` — bootstraps `.venv` + `frontend/node_modules` on first run, then backend `:8000` + frontend `:5173`; Ctrl-C stops both.
- Install only: `make dev-setup` (Python 3.12 `.venv` from `requirements.txt` + `requirements-dev.txt`, then `npm install` in `frontend/`).
- Run one side: `make dev-backend` (`http://localhost:8000/docs`), `make dev-frontend` (`http://localhost:5173`).
- App tests: `make test` (`pytest`, scoped to `tests/`). Single test: `.venv/bin/python -m pytest tests/test_route_api.py::test_route_matches_contract -v`.
- Harness tests: `make swarm-test` (uses `swarm/.venv`).
- Lint: `make lint` (`ruff check .`). Types: `make typecheck` (`mypy app tests`).
- Frontend: `cd frontend && npm run check` (svelte-check), `npm run lint` (ESLint + Prettier check), `npm run format`, `npm run build`, `npm run dev`.
- Swarm: `make swarm-run|swarm-local|swarm-dash|swarm-up|swarm-up-local|swarm-test|swarm-stop|swarm-approve|swarm-preflight|swarm-sandbox`.
- Swarm economics/autonomy (015): `make swarm-supervise` (unattended queue, retry/backoff, `retry_later`) and `make swarm-report` (cost per green task, tokens per role, fix rate, stops). Per-task caps: `SWARM_MAX_COST_PER_TASK`/`SWARM_MAX_SECONDS_PER_TASK`; routing: `SWARM_LOCAL_FIRST`, `SWARM_PAID_ALWAYS`; hygiene: `SWARM_SELF_HEAL`, `SWARM_STASH_UNRELATED`, `SWARM_REVERT_OUT_OF_SCOPE`.
- Unattended/overnight: `make swarm-night` (`caffeinate -is` + supervisor). A locked screen is fine; system sleep is not — runbook: `docs/runbooks/overnight-runs.md`.
- Approval hold: `./swarm/run.sh 001 T3 --require-approval` (or `SWARM_REQUIRE_APPROVAL=1`); release with `make swarm-approve` (defaults to the last checkpoint task; `SPEC=001 TASK=T3` to be explicit) or the dashboard `a` key.

## Boundaries / entrypoints
- `app/` + `tests/` → root `.venv` (app deps only). `swarm/` → `swarm/.venv` (CrewAI). `frontend/` → npm. Do not mix them.
- Backend entrypoint: `app/main.py` (`app = FastAPI(...)`). `app/router.py` was removed; do not reintroduce a second app/route mount.
- API contract: `contracts/route.json` is the source of truth (ADR-005): `POST /route`, preference enum `hot`/`cloudy`, GeoJSON `geometry`, `{ code, message }` errors.
- Dark-factory Phase 2 (`specs/013-dark-factory-phase-2/`, done): done ledger from commit trailers (`Swarm-Task`/`Task-Hash`/`Spec-Hash`, so green-but-unchecked tasks are skipped and spec/plan edits reopen them), approval-resume commit of a held run's verified delta via the merge queue, and atomic per-step `progress.json` crash checkpoints (plan/file/age validated; gates+reviewer always rerun).
- Swarm queue: the harness reads only unchecked `- [ ] T<n> (AC-…): brief` lines from `specs/*/tasks.md`, in directory order; authoring rules + scope/`--replan` notes are in `swarm/README.md` ("Adding a spec to the swarm todo list"). `009-swarm-harness`, `012-dark-factory-harness`, and `013-dark-factory-phase-2` are always skipped (control plane). The swarm does not edit spec files — mark `[x]` yourself after green (or rely on the 013 done ledger). Non-green statuses: `needs_human`, `awaiting_approval`, `commit_failed`, `push_failed`, `merge_failed`, `crew_error`, `quota_exhausted`, `budget_exhausted`, `interrupted`, `preflight_failed`.
- Do not invent commands or config. Verify via manifests/scripts before claiming a workflow exists.

## Spec-driven workflow
- Spec before code: define requirements, acceptance criteria, and scope in `specs/` before implementing.
- Clarify first: when requirements are ambiguous, ask the user targeted questions (via `question` tool, 1–2 at a time) and refine the spec docs until clear. Do not guess or implement on ambiguity.
- Update tasks/ACs in the same change as the implementation. Record completed work and remaining blockers explicitly (see `specs/001-example-app/tasks.md` T3/T7–T10 and `specs/011-dev-run/`).
- Keep specs small and verifiable; link implementation back to spec items.
- Prefer editing existing files over creating new ones; keep changes minimal per spec.
