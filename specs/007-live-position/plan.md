# 007 Live Position — Plan

## Approach
Frontend-only stage on top of the 001 app: a TypeScript pure-logic core (no GPS, no DOM —
fully unit-testable) + a thin Svelte walk-mode shell + two position providers behind one
interface. Walk mode reuses the 001-T5 Leaflet map instance and `POST /route` (ADR-005
contract unchanged); reroute replaces the displayed route in place. Preconditions: 001 T5
(Svelte + Leaflet map, /route contract) must be landed; the pilot scaffolds any missing
frontend toolchain (`npm run check` via svelte-check, `npm test` via vitest) as part of T1/T6.
Reference spec AC-1..AC-8.

## Steps
1. TS core in `frontend/src/lib/navigation/`: `interpolate.ts` (position along LineString
by distance), `snap.ts` (snap-to-nearest-segment), `drift.ts` (sustained drift: >30 m for
~10 s or 3 consecutive fixes), `arrival.ts` (within 25 m). One `*.test.ts` per module,
no GPS/DOM; time via injected tick source so tests are deterministic (AC-2, AC-4, AC-7, AC-8).
2. Providers behind `PositionProvider { start/stop, onFix }`: `simulated.ts` (deterministic
1 s ticks along route, seedable for tests/demo) + `gps.ts` (`watchPosition` wrapper;
permission-denied → clear message + sim fallback; cleanup on stop) (AC-2, AC-3).
3. Walk-mode UI (`frontend/src/lib/walkMode.ts` store + Svelte shell): Start/Stop, walker
marker at route origin, auto-center default-on toggle, manual pan pauses follow until
re-enabled (AC-1, AC-6).
4. Drift UX: marker always renders snapped; sustained drift shows tappable
"Off route — reroute?" warning; tap requeries `POST /route` from current position to the
same destination and replaces the route; dismiss snoozes until back-on-route or 60 s (AC-4, AC-5).
5. Arrival: within 25 m → arrived banner + tracking stops; Stop button ends session anytime (AC-7).
6. Verify: `npm test` + `npm run check` green, `pytest`/`ruff`/`mypy` still green (backend
untouched); manual sim-walk demo + one real-GPS smoke off-CI (AC-8).

## Risks / Open Questions
- Urban GPS jitter vs 30 m threshold — tuned per spec; revisit only with field evidence (new ADR if threshold changes).
- `watchPosition` battery/accuracy variance across browsers — sim mode is the deterministic fallback; CI gates run sim-only, never real GPS.
- Depends on 001 T5 (map instance, /route contract); 007 lands after 001 MVP.
- Frontend toolchain (svelte-check, vitest) may not exist yet — scaffolded inside this stage and pinned in `frontend/package.json`.
