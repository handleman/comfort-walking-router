# 001 Comfort-First Walk — Tasks

- [x] T1 (AC-1, AC-4): Scaffold `app/` + `frontend/` + `contracts/route.json`, pin pytest/ruff/mypy.
  - Done by the swarm (commit `6ae008b`). Root `pyproject.toml` + dev requirements now pin pytest/ruff/mypy.
- [x] T2 (AC-1): Backend geocode via Nominatim + base walking route(s) via OSRM demo interim (provider behind interface for 008 Mapbox swap) with distance/time.
  - Done (commit `201b66d`); hardenings in 011: timeouts, User-Agent, correct GeoJSON pass-through, `POST /route`.
- [ ] T3 (AC-2): Overpass comfort lookup + shade/sun/quiet scorer + why-explanation.
  - Not complete. `app/providers/overpass.py` still returns `{}` and `app/main.py` does not call the scorer; `POST /route` returns a neutral `comfort_score=50` with an honest explanation. This is the remaining blocker for AC-2.
- [x] T4 (AC-3): SQLite cache (start, end, preference); verify cache-hit skips external calls.
  - Done (commit `8187a2d`); cache hit covered by `tests/test_route_api.py::test_identical_query_hits_cache`.
- [x] T5 (AC-1, AC-2): Svelte + Leaflet UI: start/end, hot/cloudy toggle, route + explanation.
  - Done (commit `b94dd1a`); completed/fixed in 011 (map height + CSS, submit handler, route drawing, preference select, explanation panel). AC-2 display is ready but scores are neutral until T3.
- [ ] T6 (AC-4): Green `pytest` + `ruff check .` + `mypy .` + manual demo render.
  - Gates + route render are green as of 2026-11-08 (`make test`, `make lint`, `make typecheck`, `make swarm-test`, `npm run check`, headless demo). Left open until T3 gives the demo something comfort-specific to show.
