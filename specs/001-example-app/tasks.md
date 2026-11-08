# 001 Comfort-First Walk — Tasks

- [x] T1 (AC-1, AC-4): Scaffold `app/` + `frontend/` + `contracts/route.json`, pin pytest/ruff/mypy.
- [x] T2 (AC-1): Backend geocode via Nominatim + base walking route(s) via OSRM demo interim (provider behind interface for 008 Mapbox swap) with distance/time.
- [x] T4 (AC-3): SQLite cache (start, end, preference); verify cache-hit skips external calls.
- [x] T5 (AC-1, AC-2): Svelte + Leaflet UI: start/end, hot/cloudy toggle, route + explanation.
- [x] T3 (AC-2): Overpass corridor client in `app/providers/overpass.py` (bbox query, timeout + User-Agent, JSON → feature counts) with fixture tests in `tests/test_overpass_provider.py`.
- [ ] T7 (AC-2): Map OSM tags (trees/green, path/road class, `lit`) into a feature dict in `app/features.py` with fixture tests in `tests/test_features.py`.
- [ ] T8 (AC-2): Comfort scorer in `app/scoring.py` (shade/sun/quiet with preference weights) with matrix tests in `tests/test_scoring.py`.
- [ ] T9 (AC-2): Wire the scorer into `POST /route` in `app/main.py` (real `comfort_score` + factor explanation, contract shape unchanged) and extend `tests/test_route_api.py`.
- [ ] T10 (AC-2): Show the score and each applied factor in `frontend/src/App.svelte`; keep `npm run check` green.

<!-- Human gate, not queued (no code change): after T3/T7–T10 run `make test`, `make lint`,
     `make typecheck`, `cd frontend && npm run check`, then a live demo and tick 001 AC-2. -->
