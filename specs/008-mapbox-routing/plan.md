# 008 Mapbox Routing — Plan

## Approach
Backend-only provider swap behind the scorer interface from 001-T2 (`RouteProvider` ABC):
new `app/providers/mapbox.py` implementing `route(start, end)` over Mapbox Directions
(walking profile), preserving the ADR-005 contract byte-for-shape so the frontend is
untouched. Token handling per ADR-006 (env, backend-only, fail-fast). Preconditions:
001 T2 (provider interface), T4 (SQLite cache), `contracts/route.json`. Reference spec AC-1..AC-4.

## Steps
1. Mapbox client `app/providers/mapbox.py`: walking profile, 1–2 alternatives, short timeout
+ single retry; returns GeoJSON `LineString` + distance/time; fixture-recorded unit tests
(`app/tests/fixtures/mapbox-*.json`, no live calls in CI) (AC-1, AC-4).
2. Token wiring: `MAPBOX_TOKEN` from env, backend-only (never to frontend); missing/empty
aborts startup with a clear message; document in `.env.example` + `docs/tech-stack.md`
per ADR-006 (AC-2).
3. Cache/quota: reuse the 001 SQLite cache unchanged (cache-hit skips Mapbox); add
calls-vs-cache-hits INFO logging for quota visibility (AC-3).
4. Contract conformance: replay a recorded Mapbox fixture through scorer → validate
response against `contracts/route.json`; frontend untouched (AC-1).
5. Verify: `pytest` + `ruff check .` + `mypy .` clean; one manual live smoke (single route)
off-CI to confirm quota + shape (AC-4).

## Risks / Open Questions
- Free-tier quota exhaustion in dev — cache-first + fixture tests bound usage; live smoke is manual, not CI.
- Mapbox walking coverage differing from OSRM demo on some paths — scorer is provider-agnostic; diffs surface as comfort-score deltas, not errors.
- Depends on 001 (interface, cache, contract); lands after 001 MVP.
