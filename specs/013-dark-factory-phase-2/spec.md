# 013 Dark-Factory Phase 2 — Spec

**Status: complete** — implemented 2026-11-08 (T1–T8).

## What / Why
012 made green trustworthy and added observability, budgets, a sandbox, and a branch/merge queue. Three gaps still block genuinely unattended operation:

1. **Green work is not recorded as done.** The swarm never edits `specs/`, so a green task stays `- [ ]`. Resume normally advances past it, but a wrapped resume (all later tasks done) can pick the unchecked-but-green task again, hit the vacancy guard, and stop as `needs_human`.
2. **Approval holds cannot be committed later.** A run held at `awaiting_approval` never commits. Approving after the fact starts a *new* run; the held changes become the new baseline, so the rerun is a vacancy and the reviewed work is lost to the queue.
3. **Crashes restart the task from scratch.** A killed pilot leaves `events.jsonl` + `meta.json` but no step progress, so the next run redoes every micro-step (cost, time, and possible partial-edit churn).

This spec closes those three gaps while keeping the 012 invariants: specs stay immutable, green stays truthful, and commits still go through the branch/merge queue.

## Scope
- In scope:
  - `swarm/done.py` (new): task content hash + a **done ledger derived from commit trailers**, so completion survives deleting `swarm/runs/` or changing machines.
  - `swarm/flow.py`: emit trailers from `_commit_changes`; filter the queue/resume by done entries; commit a held run on approval; write and consume per-step `progress.json` checkpoints.
  - `swarm/tui.py`: `a` commits a held run when one exists (otherwise keeps the next-run ledger behavior).
  - `swarm/run.sh`, `Makefile`: `swarm-approve` releases a held run by committing it.
  - `swarm/tests/`: unit + real-git tests for all three behaviors.
  - Docs: `swarm/README.md`, `AGENTS.md`, `changelog.md`, `docs/roadmap.md`.
- Non-goals (still out of scope):
  - Editing `specs/` from the swarm (no auto-ticking checkboxes; the ledger replaces that need).
  - PR creation, risk classes, branch protection, canary deploy.
  - Parallel workers / multiple worktrees.
  - Sandbox egress allowlist, diff secret scanning, per-call OTel tracing.
  - Remote CI.

## Acceptance Criteria
- [x] AC-1: **Done ledger.** Every green commit carries `Swarm-Task: <spec>/<T n>`, `Swarm-Task-Hash: <sha256>`, and `Swarm-Run: <run id>` trailers. The ledger is read from git history on the base branch; no new mutable state file is required.
- [x] AC-2: **No spec edits.** The swarm still never writes under `specs/`. A green task can remain unchecked; the ledger makes resume/auto-advance skip it.
- [x] AC-3: **Stale-task reopening.** The task hash covers the task id, brief, and AC refs. If the brief/ACs change, the old done entry no longer matches and the task becomes runnable again. A missing git history (fresh copy without commits) fails open (tasks run).
- [x] AC-4: **Durable + bounded.** Done lookup survives `swarm/runs/` deletion and process restarts, scans a bounded number of commits, and adds negligible time to resume.
- [x] AC-5: **Approval resume commits the held run.** An `awaiting_approval` run records its in-scope delta hashes and git HEAD. Approving it commits exactly that delta through the normal branch/merge/push path, marks the run `green`, and the next resume advances — no crew rerun.
- [x] AC-6: **Approval safety.** If the worktree, recorded file hashes, or HEAD changed since the hold, approval refuses with a note and the run stays `awaiting_approval`; no partial or out-of-delta commit is made. Scope/secret checks still apply.
- [x] AC-7: **Step checkpoints.** After each completed micro-step the flow writes `progress.json` (plan hash, steps, completed index, per-step output tails, run-delta hashes) atomically.
- [x] AC-8: **Checkpoint resume.** A run killed or interrupted mid-task resumes at the next uncompleted step when the plan hash and worktree delta still match; gates and the reviewer always rerun. `run.json` records `resumed_from_step` and `recovery`.
- [x] AC-9: **Checkpoint safety.** A stale or mismatched checkpoint (plan changed, files changed, spec/task changed) is ignored and the task restarts from step 1 with the reason recorded — never a half-applied resume.
- [x] AC-10: **Evidence.** `run.json` records done-ledger hits, approval commit results, and checkpoint resume details; the dashboard surfaces them without false greens.
