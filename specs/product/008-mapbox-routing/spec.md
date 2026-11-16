# 008 Mapbox Routing — Spec (post-MVP stage)

## What / Why
Replace the MVP-interim OSRM demo geometry with Mapbox Directions API (walking, free tier) for reliability, keeping scoring, cache, and API contract unchanged.

## Scope
- In scope:
  - Backend provider swap behind the scorer interface (ADR-002): Mapbox walking profile, 1–2 alternatives, timeout + single retry.
  - `MAPBOX_TOKEN` via env, backend-only; never exposed to frontend; missing-token startup error with clear message.
  - Quota discipline: existing SQLite cache + debounce retained; quota-friendly request shaping (no polling, cache-hit first).
  - Contract unchanged: `POST /route` request/response shape identical to 001 (frontend untouched).
- Non-goals:
  - No scoring changes, no new comfort factors, no reroute-logic changes (007 behavior unchanged).
  - No self-hosted routing (rejected, ADR-002).

## Acceptance Criteria
- [ ] AC-1: With token set, routes come from Mapbox with distance/time; scoring + explanation identical in shape to 001.
- [ ] AC-2: Missing/empty `MAPBOX_TOKEN` fails fast at startup with a clear message (no silent fallback to OSRM).
- [ ] AC-3: Repeat query served from SQLite cache (no Mapbox call); quota-relevant logging (calls vs cache-hits) exists.
- [ ] AC-4: `pytest` + `ruff check .` + `mypy .` clean; provider unit-tested with fixtures (no live Mapbox in tests).
