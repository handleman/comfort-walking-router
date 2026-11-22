# 046 Dark-Factory Harness — Tasks

Each task is atomic and maps to exactly one acceptance criterion.

- [x] T1 (AC-1): `swarm/flow.py` — `RunLock.acquire()` reads existing PID if lock file exists; checks liveness with `os.kill(pid, 0)`; if dead, reclaims lock (writes own PID, returns `True`); if alive, returns `False` with reason `lock_held`. Logs `lock_stale` event when reclaiming.
- [x] T2 (AC-2): `swarm/flow.py` — `SwarmFlow.__init__()` kills any running `swarm.tui` processes (by scanning `ps aux` for `swarm.tui`) before acquiring the `RunLock`.
- [x] T3 (AC-3): `swarm/flow.py` — `_kickoff()` wraps `bounded.run_bounded()` with `SWARM_CREW_TIMEOUT_SECONDS` (default 300); if timeout expires and thread still alive, raises `_WallBudget` with reason code `phase_timeout`.
- [x] T4 (AC-4): `swarm/flow.py` — `checkpoint_stale` detection already lives in `load_checkpoint()`: a checkpoint whose every step is done but whose run never finished is rejected with that reason and the coding phase is redone so the current run owns the delta.
- [x] T5 (AC-5): `swarm/flow.py` — `RunLock` auto‑reclaims a dead‑PID lock and records it in `run.json` under `lock_stale` (`previous_pid`, `reclaimed_by`, `at`).
- [x] T6 (AC-6): `swarm/tests/test_flow.py` (new) — 5 tests: stale lock reclaim, live-PID lock held, stale `swarm.tui` killed, bounded phase timeout, `SWARM_CREW_TIMEOUT_SECONDS` default.
- [x] T7 (AC-7): All swarm tests pass (`pytest swarm/tests/ -q` → 773 passed).
- [x] T8 (AC-8): `ruff check swarm/` clean (zero errors).
- [x] T9 (AC-9): `docs/reference.md` lists the new non-green statuses (`lock_stale`, `lock_held`, `phase_timeout`, `checkpoint_stale`).
- [x] T10 (AC-8): `swarm/supervise.py` — a `needs_human` stop is retried like a retryable stop (bounded by `max_attempts`) and then parked as `retry_later`, so an unattended night never halts on the first red task; `SWARM_SUPERVISE_NEEDS_HUMAN=0` restores stop-on-first-red. Tests: `swarm/tests/test_supervisor.py`.
- [x] T11 (AC-8): the per-crew cap follows the model profile (`llms.crew_timeout_seconds`): 300 s when every role is cloud, 900 s when any role or fallback is local, explicit `SWARM_CREW_TIMEOUT_SECONDS` wins — so switching paid ↔ local never truncates a local step. Test: `swarm/tests/test_flow.py::test_phase_timeout_defaults_by_profile`.
