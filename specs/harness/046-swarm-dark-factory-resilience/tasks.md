# 046 Dark-Factory Harness — Tasks

Each task is atomic and maps to exactly one acceptance criterion.

- [ ] T1 (AC-1): `swarm/flow.py` — `RunLock.acquire()` reads existing PID if lock file exists; checks liveness with `os.kill(pid, 0)`; if dead, reclaims lock (writes own PID, returns `True`); if alive, returns `False` with reason `lock_held`. Logs `lock_stale` event when reclaiming.
- [ ] T2 (AC-2): `swarm/flow.py` — `SwarmFlow.__init__()` kills any running `swarm.tui` processes (by scanning `ps aux` for `swarm.tui`) before acquiring the `RunLock`.
- [ ] T3 (AC-3): `swarm/flow.py` — `_kickoff()` wraps `bounded.run_bounded()` with `SWARM_CREW_TIMEOUT_SECONDS` (default 300); if timeout expires and thread still alive, raises `_WallBudget` with reason code `phase_timeout`.
- [ ] T4 (AC-4): `swarm/flow.py` — Add `checkpoint_stale` detection: when a run's `run.json` has `progress.json` but no commit occurred (`verifier.corrections` not set), redo the coding phase (planner → coder → reviewer → verifier) so the current run owns the delta. Reuse `_reverify_if_stale` logic with visual QA.
- [ ] T5 (AC-5): `swarm/flow.py` — `RunLock` auto‑reclaims a dead‑PID lock and logs the event to `run.json` under `lock_stale` reason code.
- [ ] T6 (AC-6): `swarm/tests/test_flow.py` (new) — Add 4 tests:
  1. `test_stale_lock_reclaim` — dead PID lock is reclaimed.
  2. `test_lock_held` — alive PID lock returns `False` with `lock_held`.
  3. `test_stale_process_cleanup` — stale `swarm.tui` process killed before run.
  4. `test_phase_timeout` — crew call exceeding `SWARM_CREW_TIMEOUT_SECONDS` raises `_WallBudget`.
- [ ] T7 (AC-7): All 766 swarm tests continue to pass (`pytest swarm/tests/ -q`).
- [ ] T8 (AC-8): `ruff check swarm/` clean (zero errors).
- [ ] T9 (AC-9): `AGENTS.md`, `GLOSSARY.md`, `docs/reference.md` updated with new status codes (`lock_stale`, `lock_held`, `phase_timeout`, `checkpoint_stale`).