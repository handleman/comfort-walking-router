# 007 Live Position — Plan

## Approach
Frontend-only stage on top of the 001 API: TypeScript pure-logic core (testable without GPS) + thin Svelte walk-mode shell + two position providers. Reroute reuses `POST /route` per ADR-005 (contract unchanged); drift threshold and arrival radius come from spec (30 m / 25 m). Reference spec AC-1..AC-8.

## Steps
1. TS core in `frontend/src/lib/navigation/`: interpolate-along-`LineString`, snap-to-nearest-segment, drift detector (>30 m for ~10 s or 3 consecutive fixes), arrival check (25 m). Unit tests, no GPS/DOM (AC-2, AC-4, AC-7, AC-8).
2. Providers: simulated (deterministic 1 s ticks along route, for tests/demo) + GPS (`watchPosition` wrapper with permission-denied → message + sim fallback). Cleanup on stop (AC-2, AC-3).
3. Walk-mode UI: Start/Stop, walker marker at route origin, auto-center (default on, toggleable), manual pan pauses follow (AC-1, AC-6).
4. Drift UX: snapped render always; sustained drift shows "Off route — reroute?" warning; tap requeries `POST /route` from current position to same destination and replaces route; dismiss snoozes until back-on-route or 60 s (AC-4, AC-5).
5. Arrival: within 25 m → banner + tracking stops; Stop ends session anytime (AC-7).
6. Verify: `npm run check` + frontend unit tests + `pytest`/`ruff`/`mypy` still green (backend untouched), manual sim walk + one real-GPS smoke (AC-8).

## Risks / Open Questions
- Urban GPS jitter vs 30 m threshold — tuned per spec; revisit only with field evidence (new ADR if threshold changes).
- `watchPosition` battery/accuracy variance across browsers — sim mode is the deterministic fallback.
- Depends on 001 (`POST /route`, ADR-005 contract); 007 lands after 001 MVP.
