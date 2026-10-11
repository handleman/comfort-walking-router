# 008 Mapbox Routing — Tasks

- [ ] T1 (AC-1, AC-4): `app/providers/mapbox.py` behind `RouteProvider` (walking, alternatives, timeout+retry, GeoJSON out) + fixture unit tests (`app/tests/fixtures/`, no live calls).
- [ ] T2 (AC-2): `MAPBOX_TOKEN` wiring (backend-only, fail-fast with clear message, `.env.example` + `tech-stack.md` note) per ADR-006.
- [ ] T3 (AC-3): Reuse 001 SQLite cache unchanged; add calls-vs-cache-hits INFO logging.
- [ ] T4 (AC-1): Contract test (recorded fixture → scorer → validate vs `contracts/route.json`); frontend untouched.
- [ ] T5 (AC-4): Green `pytest` + `ruff` + `mypy`; one manual live smoke off-CI.
