# Roadmap

## 0 — Foundations (done)
- Constitution with quality gates, mission (comfort-first walks), stack: Python + FastAPI + Svelte + Leaflet, OSM/Overpass, SQLite cache first.

## 1 — 001 MVP: comfort-scored walk (next)
- Svelte + Leaflet map: enter start/end → scored route + why-explanation.
- FastAPI scoring API over OSM data; factors: shade + sun + quiet.
- SQLite cache for OSM responses. Verify: `pytest` + `ruff` + `mypy`, demo route renders.
- Spec: `specs/001-example-app/spec.md` → plan → tasks → implement.

## 2 — Later (out of MVP)
- Real weather-aware sun preference, richer factors (surface, lighting, safety).
- Postgres for saved routes/prefs + user accounts.
- Turn-by-turn, mobile, offline. Each as its own `specs/NNN-*/` with ADR if cross-cutting.
