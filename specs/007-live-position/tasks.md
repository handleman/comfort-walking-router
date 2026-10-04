# 007 Live Position — Tasks

- [ ] T1 (AC-2, AC-4, AC-7, AC-8): TS core `frontend/src/lib/navigation/` (interpolate, snap, drift detector, arrival 25 m) + unit tests.
- [ ] T2 (AC-2, AC-3): Simulated provider (1 s deterministic ticks) + GPS `watchPosition` wrapper (denied → message + sim fallback, cleanup on stop).
- [ ] T3 (AC-1, AC-6): Walk-mode UI: Start/Stop, origin marker, auto-center toggle, pan-pause.
- [ ] T4 (AC-4, AC-5): Drift warning + tap-to-reroute via `POST /route` (replace route) + dismiss snooze.
- [ ] T5 (AC-7): Arrival 25 m banner + stop; Stop anytime.
- [ ] T6 (AC-8): Green `npm run check` + unit tests + `pytest`/`ruff`/`mypy`; sim-walk demo + GPS smoke.
