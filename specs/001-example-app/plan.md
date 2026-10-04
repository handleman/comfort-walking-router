# 001 Comfort-First Walk — Plan

## Approach
Backend-first: FastAPI `POST /route` accepts place names or lat-lon + hot/cloudy preference. Flow: Nominatim geocode → OSRM demo (`router.project-osrm.org`, foot) for base geometries → Overpass for shade/green + traffic tags along corridor → comfort score → SQLite cache. Svelte + Leaflet frontend calls API, renders route + explanation. Reference spec AC-1..AC-4.

## Steps
1. Scaffold `app/` (FastAPI) + `frontend/` (Svelte/Vite + Leaflet) + `contracts/route.json`; pin `pytest/ruff/mypy` (AC-1, AC-4).
2. Backend: geocode (Nominatim) + base routes (OSRM demo, 1–2 alternatives) with distance/time (AC-1).
3. Backend: Overpass comfort lookup + scorer (shade + sun + quiet) + why-explanation (AC-2).
4. Backend: SQLite cache keyed by (start, end, preference); cache-hit skips OSRM/Overpass (AC-3).
5. Frontend: start/end inputs + hot/cloudy toggle + Leaflet route + explanation panel (AC-1, AC-2).
6. Verify: `pytest` (scorer + cache-hit + API), `ruff check .`, `mypy .`, manual demo route render (AC-4).

## Risks / Open Questions
- OSRM demo rate limits / downtime — mitigate with cache + short timeout + single retry; self-host Valhalla later (non-goal for MVP).
- Overpass + Nominatim usage policy / latency — debounce frontend, cache aggressively, attribute OSM.
- Contracts shape TBD in `contracts/route.json` during step 1.
