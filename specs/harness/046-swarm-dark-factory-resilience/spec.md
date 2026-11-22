# 046 Swarm Dark-Factory Resilience — Spec

Harness spec (control plane; the queue never runs it).

## Problem

The swarm can get stuck in several operational scenarios that break the "pilot-run-merge" loop:

1. **Stale process-held lock** — After a run is killed (e.g., SIGTERM from a timeout), a background `swarm.tui` process may still hold the `RunLock` via `flock(2)`. The next `swarm-run` then aborts with `"another swarm run is active (lock: swarm/runs/.lock)"` instead of reclaiming the lock.

2. **Stalled run after all steps done** — The planner/crew may finish its coding phase but the run never commits (`no progress.json`). The old `restarting T4: checkpoint ... rejected: checkpoint had every step done but the run never finished; redoing the coding phase so this run owns the delta` error demonstrates this. A checkpoint that doesn't own a completed run should be rejected and the coding phase redone.

3. **Timeout / hang window between phases** — The wall budget (`SWARM_TASK_WALL_BUDGET`) is checked *between* crew kickoffs only. If an individual LLM call inside a phase hangs (no `bounded.run_bounded` guard on the call itself, or the guard's timeout isn't aggressive enough), the run waits indefinitely. The crew's `max_execution_time` guards the *scheduler*, not the network call.

4. **No automatic recovery from partially-stashed unrelated edits** — `_stash_unrelated` parks files that the operator edited during a run, but the run's checkpoint may have been taken before the stash, leaving the delta ambiguous on resume.

## Goal

Restore the swarm to a fully autonomous "dark factory" state where these situations never require manual intervention:

1. **Lock reclamation** — `RunLock.acquire()` detects if a lock is held by a dead process and silently reclaims it; if held by a living process, it reports an explicit status (`needs_human` / `awaiting_approval`) rather than silently blocking.

2. **Stale checkpoint auto-recovery** — When a run checkpoint records that *every step* was completed but the run never produced a final `progress.json` / commit, the flow automatically redoes the coding phase so this run owns the delta, matching the existing `_reverify_if_stale` / `_checkpoint_recovery` pattern.

3. **Per-phase bounded execution** — Every crew kickoff (`_kickoff`) is wrapped with an explicit per-crew timeout (`SWARM_CREW_TIMEOUT_SECONDS`, default 300) that kills the daemon thread and raises `_WallBudget` instead of the flow waiting forever.

4. **Auto-cleanup of stale TUI / background processes** — Before a new run starts, any leftover `swarm.tui` processes from a previous run are terminated, preventing lock conflicts.

## Non-Green Status Model Extension

| Status | When it applies | Reason code |
|--------|-----------------|-------------|
| `lock_stale` | RunLock acquired but detected a dead-PID lock; auto-reclaimed before any LLM call | `lock_stale` |
| `lock_held` | Another pilot's process holds the lock and is still alive | `lock_held` |
| `checkpoint_stale` | Run checkpoint records all steps done but no final progress.json / commit; flow auto-redoes the coding phase | `checkpoint_stale` |
| `phase_timeout` | A crew kickoff exceeded `SWARM_CREW_TIMEOUT_SECONDS`; daemon thread killed, budget charged | `phase_timeout` |
| `needs_human` (retried) | The supervisor retries a red task overnight, then parks it as `retry_later` so the queue keeps moving | task's own `reason_code` |

## Acceptance Criteria

- [ ] `RunLock.acquire()` detects a dead-PID lock and auto-reclaims; the next `swarm-run` proceeds without manual lock-file surgery.
- [ ] `RunLock.acquire()` detects a live-PID lock and returns `False` with reason code `lock_held`.
- [ ] A run whose checkpoint records all steps done but never committed triggers automatic coding-phase redo (`checkpoint_stale`).
- [ ] Every `_kickoff` call uses `SWARM_CREW_TIMEOUT_SECONDS` (default 300) wrapping `bounded.run_bounded()`; exceeding it raises `_WallBudget`.
- [ ] Before a new `swarm-run` starts, any running `swarm.tui` process is killed; lock acquisition succeeds.
- [ ] No behavioural change to any existing builder or test: all swarm tests continue to pass (773).
- [ ] The supervisor never halts the queue on a `needs_human` stop: it retries (bounded), then parks the task as `retry_later` and moves on (`SWARM_SUPERVISE_NEEDS_HUMAN=0` opts out).

## Files Modified

- `swarm/flow.py` — `RunLock.acquire()`, `SwarmFlow.__init__()` (stale-process cleanup + per-phase timeout), `SwarmFlow._kickoff()` (per-crew timeout wrapper).
- `swarm/tui.py` — killed on run start; no API change.
- `swarm/tests/test_bounded.py` — parametrize `SWARM_CREW_TIMEOUT_SECONDS` default (no logic change, only env-override).
- `swarm/tests/test_wall_budget.py` — add test for `phase_timeout` scenario.
- `specs/harness/046-swarm-dark-factory-resilience/` — spec, plan, tasks.