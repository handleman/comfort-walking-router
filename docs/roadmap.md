# Roadmap

## 0 — Foundations (done)
- Constitution with quality gates, mission (comfort-first walks), stack: Python + FastAPI + Svelte + TypeScript + Leaflet, OSM/Overpass, SQLite cache first.

## 1 — 001 MVP: comfort-scored walk (next)
- Svelte + Leaflet map: enter start/end → scored route + why-explanation.
- FastAPI scoring API over OSM data; factors: shade + sun + quiet.
- SQLite cache for OSM responses. Verify: `pytest` + `ruff` + `mypy` + `npm run check`, demo route renders.
- Spec: `specs/001-example-app/spec.md` → plan → tasks → implement.

## 2 — Spec milestones (each its own `specs/NNN-*/`, ADR if cross-cutting)
- 001 already covers `002-map-ux` (Svelte UI) and `003-cache-perf` (SQLite cache) as its ACs — no separate stages.
- `004-weather-sun` (spec→plan→tasks done): Open-Meteo auto preference + manual override. Accept: thresholds, source chip, cached fetch, graceful fallback.
- `005-saved-routes` (spec→plan→tasks done, ADR-007): opaque-bearer pseudo-auth, no-accounts Postgres routes + prefs, 90-day route TTL. Accept: holder scoping (404), sweep, clean migrations, cache untouched.
- `006-comfort-plus` (spec→plan→tasks done): lighting + traffic toggles (equal weights). Accept: fixture-pair flips, honest tag gaps, no 001 regression.
- `007-live-position` (spec drafted): walk-mode marker, no voiceover. Sim + GPS providers, snap + sustained-drift (>30 m, ~10 s/3 fixes) tap-to-reroute warning, auto-center toggle, arrival banner + Stop. No auto-rerouting.
- `008-mapbox-routing` (spec drafted, post-MVP): swap OSRM interim → Mapbox free tier behind provider interface. Accept: contract unchanged, token backend-only, cache-hit skips Mapbox, no live calls in tests.

## 3 — Non-goals (no spec yet)
- Turn-by-turn, mobile native, offline maps.
