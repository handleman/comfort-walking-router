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
- `021-fix-loop` is specced (investigation done, not implemented): the measured waste after 020 is the second round — 59% of green runs need a fix round, `coder:fix*` is 44.6% of prompt tokens, and a fix round triples p50 wall clock (202 s → 615 s). The spec adds an outcome replay suite + baseline, per-round fix telemetry, deterministic repair before QA (formatting/`--fix` lint never reaches a model), a tests-first A/B with a separate test author, an AC-aware coder prompt A/B, repair-budget/checkpoint policy and verification-ROI reporting. Targets: fix rate 59% → ≤35%, `coder:fix*` tokens −40%, fix-task p50 ≤400 s, green not lower. Investigation: `docs/research/fix-loop-2026.md`. Control-plane spec, skipped by the queue.
- Next harness phases (decided 2026-11-12): 022 parallel factory (dependency-aware parallel steps + concurrent task workers), 023 earned autonomy by risk (class 0/1 auto-merge after gates + verifier; class 2/3 human; expand on measured agreement/escape rates). A durable event-sourced orchestrator layer is a recorded future option, not a current deliverable — ADR-012 pins its shape (in-repo journal kernel, crews as activities), the four seams that keep it cheap, and the measurable triggers that promote it.

## 4 — Non-goals (no spec yet)
- Turn-by-turn, mobile native, offline maps.

## 5 — Operations
- Overnight/unattended pilot runs: `docs/runbooks/overnight-runs.md` (sleep/caffeinate, tmux, supervisor recovery, cost/time knobs).
