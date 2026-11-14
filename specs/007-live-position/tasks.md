# 007 Live Position — Tasks

- [x] T1 (AC-2, AC-8): Add a `test` script (vitest) + `vitest` devDep to `frontend/package.json`, run `npm install` there to update the lockfile, then add `frontend/src/lib/navigation/interpolate.ts` and `interpolate.test.ts` (distance-along-LineString with injected ticks).
- [x] T2 (AC-4): Add `frontend/src/lib/navigation/snap.ts` + `snap.test.ts` (snap a fix to the nearest route segment/point, returns distance-off-route).
- [x] T3 (AC-4): Add `frontend/src/lib/navigation/drift.ts` + `drift.test.ts` (sustained drift: >30 m for ~10 s or 3 consecutive fixes; brief drift stays quiet).
- [x] T4 (AC-1, AC-7): Add `frontend/src/lib/navigation/arrival.ts` + `arrival.test.ts` (25 m radius, idempotent arrived signal).
- [x] T5 (AC-2, AC-3): Add `PositionProvider` + `simulated.ts` (deterministic 1 s ticks, seedable) + `gps.ts` (`watchPosition`, permission-denied message + sim fallback, cleanup on stop) under `frontend/src/lib/navigation/` with provider tests.
- [ ] T6 (AC-1, AC-6): Add `frontend/src/lib/walkMode.ts` store + `frontend/src/lib/WalkControls.svelte`: Start/Stop, marker at route origin, auto-center default-on toggle, manual pan pauses follow until re-enabled.
- [ ] T7 (AC-4, AC-5): Render the marker snapped always; show the tappable "Off route — reroute?" warning on sustained drift; tap requeries `POST /route` from the current position to the same destination and replaces the displayed route; dismiss snoozes until back-on-route or 60 s.
- [ ] T8 (AC-7): Arrival within 25 m shows the arrived banner and stops tracking; Stop ends the session anytime and removes the marker.
- [ ] T9 (AC-2, AC-8): Add `frontend/src/lib/navigation/walk.integration.test.ts`: drive the session with an injected `SimulatedProvider` (manual ticks) — origin marker → ticks along the route → sustained drift shows the reroute warning → tapped reroute replaces the route from the current position → arrival within 25 m shows the banner and stops tracking — plus Stop ending the session, with `fetch` stubbed for `POST /route`.

- [ ] T10 (AC-1, AC-4, AC-6, AC-7): Wire walk mode into the page. `frontend/src/lib/WalkControls.svelte` and the `walkMode` store exist but `frontend/src/App.svelte` never imports or renders them, so `button.walk-start` is absent (found by running `frontend/e2e/walk-mode.spec.ts`). Import and render `WalkControls` inside the `{#if route}` result section with `route.waypoints` mapped to `LatLng[]`; subscribe to `$walkMode.markerPos` and draw the walker with `personIcon()` (remove it on stop or arrival). Acceptance: the existing e2e spec — Start enabled after a route, a `.leaflet-marker-icon` after Start, the reroute warning after drift, the arrived banner at the destination — and `npm run check` stays green.

<!-- Human gate, not queued (no code change): one real-GPS smoke off-CI plus a manual sim-walk
     demo; then run `npm run check` + `npm test` + `make test`/`lint`/`typecheck` and tick 007 AC-8. -->
