# 051 Acceptance Artifacts Commit — Spec

Harness spec (control plane; the queue never runs it).

## Problem

The 043 acceptance pass writes two artifacts per spec — `<spec>/acceptance.md`
(the report) and appends unchecked `T<n>` fix tasks to `<spec>/tasks.md` — but
never commits them. They are left as dirty working-tree files for a human to
notice and commit (2026-11-23: after the run I committed them by hand). That
breaks the dark-factory rule that the swarm finishes its own work, and a dirty
`tasks.md` is exactly what the next run's `_stash_unrelated` parks (or a
coder's scope guard trips over).

The pass runs in two places, both affected:
- `swarm/flow.py` per-feature hook (after every green task), and
- `swarm/supervise.py` at queue drain.

## Goal

The acceptance pass commits its own artifacts, so a finished run leaves a clean
tree and the queued fix tasks are durable — no operator step.

## Design

- **Where:** inside `swarm/acceptance.py::run()`, after the verdict is known, so
  both call sites get it with no change to `flow.py`/`supervise.py`.
- **What:** only the artifact paths it wrote — `write_report()`'s returned
  `<spec>/acceptance.md`, and `<spec>/tasks.md` when `queue_fix_tasks` appended
  lines. Nothing else is staged.
- **How:** a direct `git add -- <artifacts> && git commit && git push` on the
  current branch. These are observation/queue records, not task work, so they do
  not go through the merge queue (which is for coder deltas). The flow is
  already back on the base branch when the hook runs (the task merged first).
- **Safety:** skip when nothing is staged (`git diff --cached --quiet`); never
  raise (a commit/push failure logs a note and the acceptance verdict stands);
  120 s timeouts.
- **Off switch:** `SWARM_ACCEPT_COMMIT=0` (mirrors `SWARM_ACCEPT_QUEUE=0`).

## Non-goals

- Not changing what the acceptance pass checks, or the merge queue for code.
- Not committing task deltas (that stays with the flow's green commit).
- Not touching the "mark [x] yourself" rule for task checkboxes — fix tasks are
  appended by 043 by design; this spec only makes the append durable.

## Acceptance criteria

- [ ] **AC-1 — artifacts committed.** After `run(queue=True)`, `<spec>/acceptance.md`
  and any appended `<spec>/tasks.md` are committed (and pushed when a remote is
  reachable), leaving no dirty artifact files.
- [ ] **AC-2 — only artifacts.** No unrelated path is staged by this commit.
- [ ] **AC-3 — idempotent/quiet.** A second pass with no artifact change makes no
  empty commit and logs nothing alarming.
- [ ] **AC-4 — never fails the pass.** A failing commit/push is logged and the
  acceptance verdict is still returned.
- [ ] **AC-5 — off switch.** `SWARM_ACCEPT_COMMIT=0` restores today's behaviour
  (write, do not commit).
- [ ] **AC-6 — no regression.** `make swarm-test` green; both call sites
  (flow hook, supervisor drain) still work.

## Files

- `swarm/acceptance.py` — `_commit_artifacts()`, `COMMIT_ENV`, call after verdict.
- `swarm/tests/test_acceptance.py` — AC-1..AC-5 fixture tests (tmp git repo).
