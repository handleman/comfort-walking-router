# 001 Comfort-First Walk — Tasks

- [x] T1 (AC-1, AC-4): Scaffold `app/` + `frontend/` + `contracts/route.json`, pin pytest/ruff/mypy.
- [x] T2 (AC-1): Backend geocode via Nominatim + base walking route(s) via OSRM demo interim (provider behind interface for 008 Mapbox swap) with distance/time.
- [x] T4 (AC-3): SQLite cache (start, end, preference); verify cache-hit skips external calls.
- [x] T5 (AC-1, AC-2): Svelte + Leaflet UI: start/end, hot/cloudy toggle, route + explanation.
- [x] T3 (AC-2): Overpass corridor client in `app/providers/overpass.py` (bbox query, timeout + User-Agent, JSON → feature counts) with fixture tests in `tests/test_overpass_provider.py`.
- [x] T7 (AC-2): Map OSM tags (trees/green, path/road class, `lit`) into a feature dict in `app/features.py` with fixture tests in `tests/test_features.py`.
- [x] T8 (AC-2): Comfort scorer in `app/scoring.py` (shade/sun/quiet with preference weights) with matrix tests in `tests/test_scoring.py`.
- [x] T9 (AC-2): Wire the scorer into `POST /route` in `app/main.py` (real `comfort_score` + factor explanation, contract shape unchanged) and extend `tests/test_route_api.py`.
- [x] T10 (AC-2): Show the score and each applied factor in `frontend/src/App.svelte`; keep `npm run check` green.

- [x] T11 (AC-2): Add `tests/test_route_contract.py` asserting the pinned request contract with `TestClient`: an unknown `preference` and a missing `start` both return 422 (FastAPI validation) and a valid request returns the contract keys `geometry`/`comfort_score`/`explanation`. Do not call the network; use the existing fixtures/patches in `tests/test_route_api.py` if needed.

- [x] T12 (AC-2): Wire the Overpass provider into the route: `app/comfort.py` (corridor bbox + query + `factors_from_counts`), `app/main.py` adds the factors to the scored properties and to the explanation, `app/scoring.py` takes additive shade/quiet terms, `app/fixtures.py` records the corridor for `ROUTE_FIXTURES=1`, and `CACHE_VERSION` moves to v3 so a cached pre-wiring response cannot hide it. Evidence: `tests/test_comfort.py`, `tests/test_route_comfort.py`, `frontend/e2e/search.spec.ts`.

<!-- Human gate, not queued (no code change): after T3/T7–T10 run `make test`, `make lint`,
     `make typecheck`, `cd frontend && npm run check`, then a live demo and tick 001 AC-2. -->
