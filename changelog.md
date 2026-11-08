# Changelog

## 2026-11-08
- swarm: 012 dark-factory Phase 0 — run-delta attribution (only files changed by the current run are gated/committed; pre-existing human edits ignored, deletions detected), scope-aware `Repo Edit`/`Repo Create`, secret-safe trimmed reads, argv-only `Guarded Shell` (`shell=False`, `shlex`; denies metacharacters, absolute/`..`/`.env*` paths, `npm install`, `pip`/`uv`; allows `npm --prefix frontend run check|build|test`), truthful green (reviewer `PASS` + non-empty in-scope delta on cached plans too), content-hashed plan cache with strict step validation (no silent `MAX_STEPS` truncation), `commit_failed`/`push_failed` instead of false green, repo `flock` + PID + unique run ids + `interrupted` trace on `SIGTERM`/`SIGINT`, approval ledger (`a`/`--approve`/`--require-approval`), role-aware coder prompts, and AC evidence in `run.json`
- swarm: gates now run `pytest -q`/`ruff check .`/`mypy app tests` against the root `.venv` (with `PYTHONPATH` so the app package imports); `012-dark-factory-harness` is skipped by the queue as a control-plane spec; 73 harness tests
- app: one-command dev startup — `make dev` bootstraps `.venv` (Python 3.12, `requirements.txt`) + `frontend/node_modules`, runs uvicorn reload `:8000` and Vite `:5173`, and stops both on Ctrl-C; added `dev-setup`, `dev-backend`, `dev-frontend`, `test`, `lint`, `typecheck`
- app: align `POST /route` with `contracts/route.json` (request `$defs.RouteRequest`, GeoJSON `geometry`, `distance_m`, `duration_s`, `{ code, message }` errors); removed broken swarm `app/router.py`; response now wraps the existing geocode → OSRM → cache flow
- fix: OSRM `geometries=geojson` geometry was double-wrapped into an invalid LineString; `preference` was sent as an invalid `annotations` param (all preference requests 504'd). Added OSRM/Nominatim timeouts + User-Agent, regression tests; cache keys versioned (`v2`) so pre-contract rows are ignored
- frontend: working map search — Leaflet CSS, real map height, submit handler, loading/error states, start/end markers, `fitBounds`, explanation panel; fixed Vite plugin import (named `svelte` export), added `svelte-check`/tsconfig
- tests: app suite `tests/` (contract shape, cache hit, 422 enum, OSRM geometry pass-through); root `pytest` scoped to app tests, harness stays `make swarm-test`
- specs: 011 done (T1 already green in `f0b17aa`, T2–T4 completed); 001 T1/T2/T4/T5 marked done, T3 comfort scoring (Overpass + shade/sun/quiet) and T6 remain open
- specs: all open queues normalized for the swarm — 001 split into T3 + T7–T10, 004/005/006/007/008/010 rewritten as one-line parser-compatible tasks; pure-verification checklists converted to human-gate comments; 009-T8 marked done with pilot evidence (`swarm/runs/20261010-181223`: green, $0)
- swarm: `tests/` added to `DEFAULT_SCOPE` (backend test-writing tasks); `_resume_point` advances when the checkpoint task is checked/absent and wraps to the earliest open spec; optional `npm test` gate runs when `frontend/package.json` has a `test` script and vitest is installed
- docs: `AGENTS.md`, `README.md`, `docs/tech-stack.md`, `docs/roadmap.md` record the verified commands, app/harness venv split, and neutral-score caveat
- docs: swarm usage guide — README quickstart plus `swarm/README.md` sections on how the todo list is parsed (unchecked `- [ ] T<n> (AC-…): brief` lines, directory order, skips) and how to add a spec (spec/plan/tasks, coder scope + `SWARM_SCOPE`, plan cache/`--replan`, checkbox policy); tasks template annotated

## 2026-10-11 (swarm harness)
- fix: vacancy check runs before autocommit (committing first wiped the worktree evidence, false-flagging real green runs — caught on 001-T5)
- specs: add 010-e2e-playwright (MVP final gate — chromium-only E2E for all user scenarios, fixtures/sim determinism, no live internet in CI); coder scope extended with `.gitignore` (008-T2 and 010-T1 both need it)
- swarm: planner robustness — validate before caching (garbage never cached), one replan retry (`PLAN_ATTEMPTS`=2) instead of instant crew_error; reviewer must verdict BLOCKED on empty diffs (defense in depth with the vacancy guard)
- swarm: false-green guards — planner output without `STEP` lines fails loudly (`_resolve_steps`, no raw-text fallback); fresh-plan green with zero in-scope changes demoted to `needs_human` (`vacancy_note`); tail dashboard follows `latest` across tasks
- swarm: checkpoint resume — bare `make swarm-up` / `run.sh` derives (spec, task) from run history (`_resume_point`, `--resume` flag): green → next, red/killed → retry, all-green → exit; explicit args override
- swarm: reviewer defaults to local QA (`ollama/swarm-qa:latest`, `Modelfile.qa`: 32k ctx + evidence discipline) — PASS and BLOCKED verdicts both verified live, dev→QA loop now quota-free; nemotron kept as alt; `make swarm-qa-image`
- swarm: inner escalation — a micro-step failing `STEP_ATTEMPTS` (3) is rescued inline by the senior (`build_senior_step_crew`, quota passes through, task-level senior ×2 unchanged); diagram + tests
- swarm: quota-stop — `free-models-per-day` 429 at any LLM call halts the pilot at once (no retry/escalation) with `quota_exhausted` status, `quota_note` in `run.json`, `QUOTA EXHAUSTED` in `up.log`; gate listener preserves terminal states; resume after reset
- EOD: 001-T1/T2 landed green ($0); loop fully armed (dev×3 → senior×2 → QA, autocommit, cross-spec) but T3 blocked — OpenRouter `free-models-per-day` 429 hit during planning; partial trace in `swarm/runs/20261010-205051/` (no `run.json`); resume with `./swarm/run.sh 001 T3` after quota reset
- swarm: agent rules from T2 findings (`FIX_RULES` shared by fix + senior crews: resolvable imports, sync/async match, ABC signatures, `ruff check --fix` first, delete strays); `MAX_FIX_ROUNDS` 1→2, senior retries ×2 (`SENIOR_ATTEMPTS`); role-sequence mermaid diagram in `swarm/README.md`
- swarm: cross-spec loop — green runs advance planner→dev→QA across specs in directory order (specs without `tasks.md` and `009-swarm-harness` skipped); TUI rebuilds task list per spec/task in live + tail modes
- swarm: senior escalation — dev phase retries ×3 (`DEV_ATTEMPTS`), then one senior pass (`SWARM_SENIOR_MODEL=openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`, tool-calling verified, must differ from planner) + QA re-verify; Zen free tier unusable from harness (FreeTierError), OpenRouter Claude all priced
- swarm: autonomous loop — green runs autocommit in-scope scaffold + push (`swarm: <spec>-<task> green (autocommit)`, `.env*` refused), then loop back to planner for next task (`run_tasks`, `--single`/`--no-commit` escapes); TUI tail mode shows plan-cached note via run `meta.json` (was live-mode only)
- swarm: pilot 001-T1 end-to-end at $0 — 6 micro-steps + reviewer PASS (pytest/ruff/mypy exit 0); `needs_human` only on the scope gate flagging the human's own uncommitted `llms.py` fix (committed same day, scope clean after)
- fix: gates green at root — `pytest`/`ruff`/`mypy` resolve via `swarm/.venv` PATH in `ShellTool`, packaging (`swarm/__init__.py`, `tests/__init__.py`), root ruff per-file-ignores for deliberate broad-excepts; installs: ruff/mypy/fastapi in swarm venv; scope guard (`DEFAULT_SCOPE` + `scope` gate, pilot confined to scaffold paths)
- fix: coder empty-response root cause — CrewAI routed `ollama/*` via its native openai_compatible client, silently dropping `extra_body`, so `think:false` never reached Ollama and Qwen thinking broke tool calls; `coder_llm` + local override now force `is_litellm=True` (+ regression `test_llms_routing.py`); step-5 repro passes end-to-end
- swarm: implement 009 T1–T7 — `swarm/` (CrewAI 1.15.27, Python 3.12 venv), prefix-routed free-first LLMs, guarded tools, Flow + event trace, parallel Textual dashboard with `--tail` attach, `run/dash/up.sh` + root `Makefile`
- swarm: findings — OpenRouter `:free` 429s under loop load; Qwen thinking breaks LiteLLM tool parsing (`extra_body={"think": False}`); Zen needs `custom_openai` gateway + v1-root base; verified brains (nemotron `:free`, `space-bunny-free`, local Qwen)
- docs: README entry + quickstart (`make swarm-*`), tech-stack swarm section, AGENTS commands, 009 tasks T1–T7 checked; T8 pilot in progress

## 2026-10-04
- docs: add changelog skill and bootstrap changelog.md
- chore: changelog skill (`.opencode/skills/changelog/`)
- docs: update plans for Comfort-First Walk and add ADRs for Live-Position Structure, Testing Strategy, and Dev-CI Environment
- docs: add specifications and plans for Weather-Sun, Saved Routes, and Comfort-Plus features
- docs: update tech stack, roadmap, and specifications for Mapbox integration and comfort features
- docs: update tech stack details to include TypeScript and npm run check
- Merge branch 'main' of github.com:handleman/comfort-walking-router
- docs: mission, stack (FastAPI+Svelte+Leaflet), roadmap, 001 spec-plan-tasks
- Initial commit
- chore: scaffold Spec-Kit SDD layout with constitution, templates, and blank docs
