# 023 Parallel Factory — Spec

Control-plane spec (added to `HARNESS_SPECS`): the queue never implements it.

## Problem

Every phase of the harness is now correct (021) and bounded (022), but the queue
is still **one task at a time**. A two-file task costs 10–16 minutes, and the
paid bake-off showed the work is capable — the latency is serial phases, not
tokens. Independent tasks are the one axis that can be parallelised without
touching the within-task order.

The repo already has the pieces: worktrees (020 T7), a branch-per-task merge
queue, a single-run lock, run-delta attribution and scope guards. What is
missing is a coordinator that runs several tasks in isolated trees and integrates
the greens **serially**, without a half-merged main tree.

## Goal

Raise queue throughput on independent tasks while keeping the integration path
exactly as trustworthy as a serial run: one writer to the main tree, the full
gate suite on the integrated delta, and no partial merge.

## Scope (phase 1)

- A worker runs one task in a throwaway worktree with the current harness copy,
  `--no-commit`, and its own run record.
- Up to `SWARM_WORKERS` tasks are attempted concurrently, chosen from a group
  whose briefs name **disjoint files**.
- Only green workers are integrated, one at a time: apply the scope-filtered
  delta, run the project's full gates on the **main** tree, commit with the
  standard trailers, push.
- A red worker, a conflict, or a failed main-tree gate leaves the task open and
  the main tree clean; the serial queue can run it later.
- `make swarm-parallel BATCH="spec:task,..."` reports per-task outcomes.

## Non-goals

- More than two workers, a durable scheduler, leases, or multi-host execution
  (ADR-012 keeps the orchestrator as a future option).
- Parallel micro-steps inside one task: they share a worktree and a file set.
- Parallel writes to the main tree (integration is serial by design).
- Rewriting the merge queue; phase 1 applies a verified delta, it does not
  create task branches.

## Acceptance criteria

- **AC-1 — Worker isolation.** A worker creates a detached worktree at HEAD,
  copies the current `swarm/` package in, links the repo's venvs, runs
  `swarm.flow --spec … --task … --no-commit --no-tui`, and never writes the main
  tree. The main tree's `git status` is unchanged by a worker.
- **AC-2 — Independence.** Two tasks run together only when the files their
  briefs name are disjoint (`prompts.brief_paths`); an overlap keeps them in
  separate groups, and phase 1 only takes workers from one group.
- **AC-3 — Serialized integration.** A green worker's delta is applied with
  `git apply --check`, then applied; the full `SWARM_GATE_COMMANDS` suite runs on
  the main tree; a commit with `Swarm-Task`/`Task-Hash`/`Spec-Hash`/
  `Swarm-Parallel` trailers is created and pushed (best effort). A gate failure
  reverses the patch and leaves no commit.
- **AC-4 — No partial merge.** A conflict, a failed gate or a commit failure
  returns `conflict`/`gates_failed`/`commit_failed`, keeps the task open, and
  leaves the main tree clean (`git status --porcelain` empty for that delta).
- **AC-5 — Measured throughput.** `make swarm-parallel` records workers, tasks,
  per-task status and integrated count; the result is compared with the serial
  queue (tasks/hour, green rate, conflict rate). Targets: **≥2× tasks/hour** on
  independent work, **no lower** green rate, and no duplicate or partial merge.
  The live comparison is recorded in `docs/research/fix-loop-2026.md`; until a
  green baseline exists it is recorded as **not measured**, not claimed.
- **AC-6 — Docs and controls.** `023-parallel-factory` is in `HARNESS_SPECS`;
  the command, `SWARM_WORKERS` and the integration contract are documented in
  `swarm/README.md`/`.env.example`; `make swarm-test` covers grouping,
  integration, rollback and the red/conflict path without an LLM.

## Evidence

`docs/research/fix-loop-2026.md` (10–16 min per two-file task; serial queue),
020 T7 worktrees, 012 run-delta attribution/scope guards, 013 approval-resume
commit path, ADR-012 (durable orchestrator deferred).

## Success definition

Two independent tasks finish in roughly the time of one, and the main tree only
ever sees a delta that passed the full gates there.
