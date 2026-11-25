# 050 Corridor Reliability Test Stand — Tasks

Each task maps to one acceptance criterion.

- [-] T1 (AC-1): **dropped** — no vcrpy cassette. The recorded-corridor fixture (`tests/conftest.py::real_corridor` → `_REAL_CORRIDOR`) plus the mocked-`requests` tests already exercise the real parse path offline; adding vcrpy is a further hardening, not a gap.
- [-] T2 (AC-1): **dropped** with T1 (the parse path is covered by the fixture + `test_overpass_retry`).
- [x] T3 (AC-2): mirror order, per-endpoint log, timeout (90 s) and 5xx → data-gap are covered by `tests/test_overpass_retry.py` (039 T1).
- [x] T4 (AC-3): `swarm/corridor_check.py` — hits the three mirrors in order with timing, reports `corridor`/`serving_mirror`/per-mirror status; one round only (no second fetch).
- [x] T5 (AC-3): `make corridor-check` (`.venv/bin/python -m swarm.corridor_check`, exit 0/1).
- [ ] T6 (AC-4): `frontend/e2e/geolocation.spec.ts` — the four-state contract: an allowed fix renders the current-position marker and pre-fills the origin; a new position moves the marker; a denial and an unavailable provider both open the start-location modal. Written once the suite could launch (the `webServer.cwd` bug). Verify: `npm --prefix frontend run test:e2e -- geolocation.spec.ts` green.
- [x] T7 (AC-5): `pytest swarm/tests/` (796), `ruff` clean; 3 deterministic `probe()` tests (serving mirror, all-fail, first-healthy).
- [x] T8 (AC-5): probe holds no secrets; the fixed route is public OSM coordinates.
