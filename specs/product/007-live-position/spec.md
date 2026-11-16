# 007 Live Position — Spec (next stage, no voiceover)

## What / Why
Add walk-mode to the comfort-first router: after a route is scored, the walker sees their own position marker moving along it as they walk. No voiceover, no turn prompts — marker + auto-center only. Keeps navigation minimal and testable.

## Scope
- In scope:
  - Start/Stop navigation on a scored route; marker starts at route origin.
  - Position providers: simulated walk (deterministic ticks for demo + tests) and browser GPS in prod (permission-denied → clear message + sim fallback).
  - Drift handling: marker renders snapped to nearest route point; sustained drift (>30 m for ~10 s or 3 consecutive fixes) shows a tappable "Off route — reroute?" warning. Tapping requeries `POST /route` from current position to the same destination and replaces the displayed route. Dismissing snoozes re-warning until back-on-route or 60 s pass.
  - Auto-center follows marker, toggleable; manual pan pauses follow until re-enabled.
  - Frontend business logic in TypeScript as pure, unit-testable functions (position interpolate, snap, drift detection, arrival).
  - Arrival detection (within 25 m) → arrived banner + tracking stops; Stop button ends session anytime.
- Non-goals:
  - No voiceover, no turn-by-turn prompts, no automatic rerouting (reroute only on tap).
  - No background tracking when tab closed; no battery-optimization work.
  - No saved history (see roadmap `005-saved-routes`).

## Acceptance Criteria
- [ ] AC-1: Start on a scored route → marker at route origin; Stop ends session and removes marker.
- [ ] AC-2: Simulated mode advances marker deterministically along route (usable in tests/demo without GPS).
- [ ] AC-3: GPS mode uses browser geolocation; permission denied shows message + offers simulated mode.
- [ ] AC-4: Brief drift renders snapped, no warning. Sustained drift (>30 m for ~10 s / 3 fixes) shows "Off route — reroute?" warning.
- [ ] AC-5: Tapping warning requeries `POST /route` from current position to same destination and replaces the route; dismiss snoozes re-warning until back-on-route or 60 s.
- [ ] AC-6: Auto-center on by default, toggleable; manual pan pauses follow, toggle resumes.
- [ ] AC-7: Entering arrival radius (25 m) shows arrived banner and stops tracking; Stop button stops anytime.
- [ ] AC-8: `pytest` + `ruff check .` + `mypy .` + `npm run check` clean; TS snapping/drift/arrival logic unit-tested.
