# 001 Comfort-First Walk — Spec

## What / Why
Minimal web map for comfortable walking routes (not shortest): start/end → comfort-scored route + why-explanation. Proves full SDD loop on FastAPI + Svelte + Leaflet + OSM (OSRM interim; Mapbox in 008).

## Scope
- In scope:
  - Svelte + Leaflet page: enter start/end, toggle hot/cloudy preference, view scored route.
  - FastAPI `POST /route` scoring API over OSRM-interim geometry + OSM/Overpass comfort data; factors v1: shade + sun + quiet. (Mapbox replaces OSRM in `008-mapbox-routing`.)
  - SQLite cache for OSM responses/scores.
- Non-goals:
  - No auth, no saved history, no Postgres.
  - No turn-by-turn, no native/mobile, no live weather-station feed.

## Acceptance Criteria
- [ ] AC-1: Enter start/end → map renders one comfort-scored route with distance/time.
- [ ] AC-2: Hot toggle prefers shade/greenery; cloudy toggle prefers sun; explanation lists applied factors.
- [ ] AC-3: Repeated identical query served from SQLite cache (no second Overpass call).
- [ ] AC-4: `pytest` + `ruff check .` + `mypy` clean per constitution.
