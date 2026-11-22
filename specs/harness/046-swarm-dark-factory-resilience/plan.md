# 046 Dark-Factory Harness — Plan

References `specs/harness/046-swarm-dark-factory-resilience/spec.md` AC-1–AC-7.

## Approach

Four resilience improvements, each mapped to one AC:

1. **T1 — Stale Lock Reclamation** (`RunLock.acquire()`)
   - Read existing PID if any. Probe liveness with `os.kill(pid, 0)`.
   - If dead → reclaim lock (write own PID, return `True`); record previous PID.
   - If alive → return `False` with reason code `lock_held`.

2. **T2 — Stale TUI Cleanup** (`SwarmFlow.__init__()`)
   - Before acquiring the lock, scan `ps` for `swarm.tui` processes and send `SIGTERM`.
   - The current process's own PID is skipped.
   - Lock acquisition then succeeds; any `swarm.tui` holding the flock is released.

3. **T3 — Per-Phase Bounded Timeout** (`_kickoff()`)
   - Wrap every `bounded.run_bounded()` call with `SWARM_CREW_TIMEOUT_SECONDS` (env, default 300s).
   - The timeout is `min(crew_timeout, wall_remaining)` when a wall budget is set.
   - If the thread is still alive after the timeout → raise `_WallBudget` with reason `phase_timeout`.

4. **T4 — Checkpoint Stale Recovery** (`_reverify_if_stale()`)
   - If a run checkpoint records all steps done but no `progress.json` / commit occurred, auto-redo the coding phase.
   - Reuse the existing `_reverify_if_stale` pattern: planner → coder → reviewer → verifier.

5. **T5 — Lock Status Logging**
   - After `RunLock.acquire()`, check `lock.lock_reclaimed`. If `True`, write `lock_stale` event to `run.json`.

6. **T6 — Tests** (`swarm/tests/test_flow.py`)
   - `test_stale_lock_reclaim` — dead PID lock is reclaimed.
   - `test_lock_held` — alive PID lock returns `False` with `lock_held`.
   - `test_stale_process_cleanup` — stale `swarm.tui` process killed before run.
   - `test_phase_timeout` — crew call exceeding `SWARM_CREW_TIMEOUT_SECONDS` raises `_WallBudget`.

7. **T7 — All 766 swarm tests pass** (`pytest swarm/tests/ -q`).

8. **T8 — Ruff clean** (`ruff check swarm/`).

## Steps

1. Re-create `spec.md`, `plan.md`, `tasks.md` in `specs/harness/046-swarm-dark-factory-resilience/`.
2. Modify `RunLock` class to add `_previous_pid`, `lock_reclaimed` property, and `_reclaim_if_stale()` helper.
3. Add `kill_stale_tui_processes()` method to `SwarmFlow` and call it in `__init__()` before lock acquisition.
4. Modify `_kickoff()` to enforce `SWARM_CREW_TIMEOUT_SECONDS` (default 300) with `min(crew_timeout, wall_remaining)`.
5. Add `checkpoint_stale` detection in `_reverify_if_stale()`.
6. Log `lock_stale` event to `run.json` when `lock_reclaimed` is `True`.
7. Add tests in `swarm/tests/test_flow.py`.
8. Run `pytest swarm/tests/ -q` — all 766 tests must pass.
9. Run `ruff check swarm/` — zero errors.
10. Update `AGENTS.md`, `GLOSSARY.md`, `docs/reference.md` with new status codes.