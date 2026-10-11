# 007 Live Position — Tasks

- [ ] T1 (AC-2, AC-4, AC-7, AC-8): TS core `frontend/src/lib/navigation/{interpolate,snap,drift,arrival}.ts` + `*.test.ts` per module (seeded ticks, no GPS/DOM); scaffold `npm run check`/`npm test` if missing.
- [ ] T2 (AC-2, AC-3): `PositionProvider` interface + `simulated.ts` (deterministic 1 s ticks) + `gps.ts` (`watchPosition`, denied → message + sim fallback, cleanup on stop).
- [ ] T3 (AC-1, AC-6): Walk-mode store + Svelte shell: Start/Stop, origin marker, auto-center default-on toggle, pan-pause until re-enabled.
- [ ] T4 (AC-4, AC-5): Snapped render always; sustained-drift "Off route — reroute?" warning; tap requeries `POST /route` (replace route); dismiss snoozes until back-on-route or 60 s.
- [ ] T5 (AC-7): Arrival check (25 m) → banner + tracking stops; Stop button ends session anytime.
- [ ] T6 (AC-8): Green `npm test` + `npm run check` + `pytest`/`ruff`/`mypy`; sim-walk demo + one real-GPS smoke off-CI.
