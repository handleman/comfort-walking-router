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

## 3 — 009 Swarm harness: learn agentic autonomous loops (in progress)
- Pure CrewAI coder swarm + Textual console dashboard implementing specs task-by-task, free-first routing (local Ollama Qwen drafts → OpenRouter `:free` planner/reviewer → Zen free fallback, paid opt-in only).
- Pilot progress: `001-T1`..`T5` and `011-T1` autocommitted green at $0 with `run.json` traces + constitution gates. Spec: `specs/009-swarm-harness/`.
- `012-dark-factory-harness` is complete (Phase 0 + Phase 1): truthful green, guarded tools, preflight, budgets, fallback/backoff, branch-per-task merge queue, repo-only sandbox, operator dashboard (ADR-011).
- `013-dark-factory-phase-2` is drafted: commit-trailer done ledger (no spec edits), approval-resume commit for held runs, and per-step crash checkpoints. Control-plane spec, skipped by the queue.

## 4 — Non-goals (no spec yet)
- Turn-by-turn, mobile native, offline maps.
