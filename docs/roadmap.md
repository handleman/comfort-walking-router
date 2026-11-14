# Roadmap

## 0 — Foundations (done)
- Constitution with quality gates, mission (comfort-first walks), stack: Python + FastAPI + Svelte + TypeScript + Leaflet, OSM/Overpass, SQLite cache first.

## 1 — 001 MVP: comfort-scored walk (in progress)
- Done: Svelte + Leaflet map (start/end, preference, route render, explanation panel), FastAPI `POST /route`, OSRM interim geometry, SQLite cache. Verified by `make test` + `make lint` + `make typecheck` + `npm run check` and a live demo route.
- Open: comfort scoring (`001-T3` + T7–T10 / AC-2) — Overpass provider is a stub, API returns a neutral score.
- Spec: `specs/001-example-app/spec.md` → plan → tasks → implement.

## 2 — Spec milestones (each its own `specs/NNN-*/`, ADR if cross-cutting)
- 001 already covers `002-map-ux` (Svelte UI) and `003-cache-perf` (SQLite cache) as its ACs — no separate stages.
- `004-weather-sun` (spec→plan→tasks done): Open-Meteo auto preference + manual override. Accept: thresholds, source chip, cached fetch, graceful fallback.
- `005-saved-routes` (spec→plan→tasks done, ADR-007): opaque-bearer pseudo-auth, no-accounts Postgres routes + prefs, 90-day route TTL. Accept: holder scoping (404), sweep, clean migrations, cache untouched.
- `006-comfort-plus` (spec→plan→tasks done): lighting + traffic toggles (equal weights). Accept: fixture-pair flips, honest tag gaps, no 001 regression.
- `007-live-position` (spec drafted): walk-mode marker, no voiceover. Sim + GPS providers, snap + sustained-drift (>30 m, ~10 s/3 fixes) tap-to-reroute warning, auto-center toggle, arrival banner + Stop. No auto-rerouting.
- `008-mapbox-routing` (spec drafted, post-MVP): swap OSRM interim → Mapbox free tier behind provider interface. Accept: contract unchanged, token backend-only, cache-hit skips Mapbox, no live calls in tests.
- `010-e2e-playwright` (spec drafted): chromium E2E for all user scenarios. `011-dev-run` is done — `make dev`, contract alignment, headless smoke verified manually.
- `014-walk-guidance-ux` (spec drafted): geolocation on load, green walker glyph, map-pick start/end, address autocomplete, moving person, arrival congratulation. Depends on 007; optional 008.

## 3 — 009 Swarm harness: learn agentic autonomous loops (in progress)
- Pure CrewAI coder swarm + Textual console dashboard implementing specs task-by-task, free-first routing (local Ollama Qwen drafts → OpenRouter `:free` planner/reviewer → Zen free fallback, paid opt-in only).
- Pilot progress: `001-T1`..`T5` and `011-T1` autocommitted green at $0 with `run.json` traces + constitution gates. Spec: `specs/009-swarm-harness/`.
- `012-dark-factory-harness` is complete (Phase 0 + Phase 1): truthful green, guarded tools, preflight, budgets, fallback/backoff, branch-per-task merge queue, repo-only sandbox, operator dashboard (ADR-011).
- `013-dark-factory-phase-2` is implemented: commit-trailer done ledger (no spec edits), approval-resume commit for held runs, and per-step crash checkpoints. Control-plane spec, skipped by the queue.
- `015-dark-factory-economics` is implemented: QA is the only gate executor backed by harness-recorded evidence (`shell_log.jsonl`), QA→coder→QA fix rounds, paid coder only for non-trivial steps, per-task budgets + `make swarm-report`, no step re-execution, provider-error classification, `make swarm-supervise`, hygiene (revert/stash/self-heal), and honest `skipped_ac`. Control-plane spec, skipped by the queue.
- `019-scenario-verifier` is implemented: between the 017 self-check and QA a read-only verifier reads the whole scenario (brief, referenced ACs, plan lines, full delta files, static import graph) and answers whether the implementation does what the brief says; on `BLOCKED` its correction plan in the planner's `STEP n:` format goes back through the coder crews and is re-verified (`MAX_VERIFY_ROUNDS`). It never writes, runs a gate or decides green (`reason_code=verifier_blocked` is `needs_human`). Control-plane spec, skipped by the queue.
- `020-harness-efficiency` is implemented: a frozen 12-case replay corpus + `make swarm-bench` (no model call), prefix-stable prompts + provider cache hints, context compaction + gate-log spilling, test-impact gate selection with the full suite before green, structured reports + a guarded `Repo Search`, and an opt-in live replay (`make swarm-bench-live CASE=<id>`). Measured against the committed baseline: task prompt −6.6%, report −86%, inner-loop gates −40%; the −30% prompt-char target is documented as missed (per-step agent/tool overhead dominates) rather than claimed. Results + investigation: `docs/research/dark-factory-market-2026.md`. Control-plane spec, skipped by the queue.
- `021-fix-loop` is implemented (measurement incomplete): the outcome suite, per-round fix telemetry, deterministic repair before QA, the tests-first/AC/loose-prompt A/Bs, repair-budget/checkpoint policy, verification ROI, verifier stability and step-landing are in. The baseline suite did not complete (`005` `verifier_blocked` at 747 s; `004`/`006` timed out at 2400 s; `007`/`010` not reached), so `replay_baseline.json` is `complete: false` and the AC-9 targets are **not evaluated**. What is validated: the verifier now passes after a correction and QA is reached; the loop's cost (0.5–0.9M tokens, 20–40 min per case) is the next problem. Investigation: `docs/research/fix-loop-2026.md`. Control-plane spec, skipped by the queue.
- `022-lean-loop` is implemented (measurement partial): phase timing from `events.jsonl` (monotonic), a per-task wall budget (`SWARM_TASK_WALL_BUDGET`, stop `wall_budget`), separate fix/verifier timeouts with budget-aware retries, opt-in concurrent verifier∥QA and a docs-only lean verifier path, and `last_phase` on a killed replay. The first live green exists — `004-weather-sun-T2` at 433 s / $0.0414, and `004-T3` at 315.6 s / $0.029 — recorded in `replay_baseline.json` (`complete: false`). The five-case suite and the AC-6 target (p50 ≤ 10 min, suite ≤ 45 min, green not lower) are still to measure; concurrency and the lean path stay off until an A/B wins. Budget defaults: 1800 s wall, $1.00 per task. Investigation: `docs/research/fix-loop-2026.md`. Control-plane spec, skipped by the queue.
- `023-parallel-factory` phase 1 is implemented: `make swarm-parallel` races independent tasks in worktrees and integrates greens serially (apply-check → full gates on main → commit/push), with rollback and one writer to the main tree. Live throughput is not measured until a green baseline exists. Control-plane spec, skipped by the queue.
- `024-earned-autonomy` is implemented (off by default): a 0/1/2/3 risk ladder, `SWARM_AUTONOMY`/`SWARM_AUTONOMY_MAX_CLASS`, an `awaiting_approval` hold that class 0/1 may skip after gates + reviewer + verifier, and a per-run `run.json.autonomy` decision + reason in the human log and `make swarm-report`. No live auto-merge is claimed until a green baseline exists; escape-rate measurement is the next decision. Control-plane spec, skipped by the queue.
- `025-durable-journal` (ADR-012 option C, first slice) is implemented: an in-repo SQLite/WAL journal (idempotent events, step leases, effect keys, `fold` in `run.json.journal`), wired into step resume and the commit effect. `run.json`/`events.jsonl`/`progress.json` remain views; green is still QA's. Postgres, a dispatcher and workers wait for the ADR triggers (>1 worker in 023).
- Earned autonomy is **on** in the operator `.env` (`SWARM_AUTONOMY=1`, max class 1): class 0/1 greens auto-merge after gates + verifier; the code default remains 0. Next: measure the first auto-merge and build the escape-rate ratio before widening to class 2.
- Next harness phases: measure the green baseline suite, 023 throughput and the 021/022 A/Bs; then the post-merge loop and halt drills once the escape rate exists.

## 4 — Non-goals (no spec yet)
- Turn-by-turn, mobile native, offline maps.

## 5 — Operations
- Overnight/unattended pilot runs: `docs/runbooks/overnight-runs.md` (sleep/caffeinate, tmux, supervisor recovery, cost/time knobs).
