# 008 Mapbox Routing — Plan

## Approach
Backend-only provider swap: implement Mapbox Directions (walking, free tier) behind the scorer interface introduced in 001 T2, preserving the ADR-005 contract byte-for-shape. Token handling follows ADR-006. Reference spec AC-1..AC-4.

## Steps
1. Mapbox client in `app/`: walking profile, 1–2 alternatives, short timeout + single retry; fixture-recorded unit tests (no live calls) proving distance/time + GeoJSON `LineString` output (AC-1, AC-4).
2. Token wiring: `MAPBOX_TOKEN` env, backend-only; missing/empty aborts startup with clear message; add `.env.example` + gitignore rule + `tech-stack.md` note per ADR-006 (AC-2).
3. Cache/quota: reuse 001 SQLite cache unchanged; add calls-vs-cache-hits logging for quota visibility (AC-3).
4. Contract conformance: `POST /route` shape identical to 001; frontend untouched; integration test replays a recorded Mapbox fixture through scorer → response schema validated against `contracts/route.json` (AC-1).
5. Verify: `pytest` + `ruff check .` + `mypy .` clean; one live smoke (single route) off-CI to confirm quota + shape (AC-4).

## Risks / Open Questions
- Free-tier quota exhaustion in dev — cache-first + fixture tests bound usage; live smoke is manual, not CI.
- Mapbox walking coverage differing from OSRM demo on some paths — scorer is provider-agnostic; diffs surface as comfort-score deltas, not errors.
- Depends on 001 (interface, cache, contract); lands after 001 MVP.
