# 013 Dark-Factory Phase 2 — Plan

References `specs/013-dark-factory-phase-2/spec.md` AC-1–AC-10. Builds on 012; keeps the `Flow` shape (planner → micro-step coders → reviewer → gates → branch/merge → next task) and the rule that the swarm never edits `specs/`.

## Approach

### 1. Done ledger from commit trailers (AC-1–AC-4)
- New `swarm/done.py`:
  - `task_hash(task) -> str`: sha256 over `id`, `brief`, and sorted `ac_refs` (whitespace-normalized), so an edited brief/AC line reopens the task.
  - `done_entries(repo_root, limit=500) -> dict[(spec, task), hash]`: run `git log -n <limit> --format=%B%x00 --grep="^Swarm-Task: "` on the current branch and parse blocks. Keep the newest hash per `(spec, task)`. Return `{}` when git is unavailable/has no history (fail open).
  - `is_done(spec, task, entries)`: hash match against the task's current hash.
- `_commit_changes` (flow) appends trailers to every green commit:
  ```
  Swarm-Task: <spec>/<task>
  Swarm-Task-Hash: <sha256>
  Swarm-Run: <run id>
  ```
  It gains `task_hash` and `run_id` arguments; the merge message also includes the task id for easy log filtering. `SWARM_MERGE_MODE=direct` and the branch path share the same message builder.
- Queue filtering:
  - `run_tasks` builds `ids` from unchecked tasks; after each green it advances to the next id whose `(spec, task)` is **not** done (or whose hash changed).
  - `_resume_point` filters done tasks before choosing “next” and before `_first_open_task`, so a wrapped resume never revisits a green-but-unchecked task.
  - Explicit `./swarm/run.sh SPEC TASK` still runs that task even if done (deliberate rework); `--resume` is the path that skips.
- No spec writes. `[x]` remains an optional human action; `swarm/README.md` explains that the ledger, not the checkbox, now drives resume.

### 2. Approval resume (AC-5, AC-6)
- At hold time (`save_run`, `awaiting_approval`), record in `run.json`:
  - `delta_hashes: {path: sha256}` for the in-scope run delta,
  - `head: <git sha>` at hold,
  - `changed_files` (already present).
- New `approve_held_run(spec_dir, task_id) -> dict` in `swarm/flow.py`:
  1. Find the newest run with `meta.json` matching spec/task and `status=awaiting_approval` (scan `swarm/runs/*/run.json`, newest first).
  2. Refuse when current `HEAD` ≠ recorded `head`, any recorded path hash differs, or the current in-scope dirty set contains paths outside the recorded set. Keep `awaiting_approval`; append `approval_error`.
  3. Else call `_commit_changes(..., paths=recorded, task_hash=..., run_id=run dir name)` (branch → push → `--no-ff` merge → push, or `merge_failed`).
  4. On success rewrite that run’s JSON: `status=green`, `approved=true`, `autocommit=<rec>`, `approval={mode:"resume", at:...}`; write the task ledger too. Print a one-line result.
- CLI: `--approve` first tries `approve_held_run`; if no held run exists it falls back to the existing “write ledger for the next run” behavior. `make swarm-approve` keeps its interface.
- TUI `a`: if the current run’s `run.json` is `awaiting_approval`, call `approve_held_run` (in a worker/thread-safe way); otherwise keep writing `approved.json` + ledger for a live run.

### 3. Step checkpoints (AC-7–AC-9)
- `progress.json` in the run dir, written atomically after each successful step (and at 0 before the loop):
  ```json
  {"run_id": "...", "spec": "...", "task": "T3", "plan_hash": "...",
   "steps": ["..."], "completed": 2, "step_outputs": ["...", "..."],
   "delta_hashes": {"app/x.py": "..."}, "updated_at": "..."}
  ```
- Resume detector (new helpers in `swarm/flow.py`, pure enough to unit-test):
  - Only consult the newest previous run for the same spec/task when its `run.json` is missing (killed) or `status=interrupted`.
  - Accept the checkpoint only if `plan_hash` matches the current plan, `steps` match, and every recorded delta hash matches the current worktree. Otherwise record `recovery="restart"` + reason.
  - On accept: seed `work_summary` with the saved outputs, set `resumed_from_step=completed`, and run the remaining steps with their original indices. Reviewer and all gates always run again.
- Delete `progress.json` after a green save; keep it after non-green statuses for the next attempt.
- `run.json` gains `resumed_from_step` and `recovery` (plus `recovery_note`).

### 4. Docs and control plane
- Add `013-dark-factory-phase-2` to `HARNESS_SPECS` (queue skips control-plane specs).
- Update `swarm/README.md` (done ledger, approval resume, checkpoint semantics, new run.json fields), `AGENTS.md`, `docs/roadmap.md`, `changelog.md`.

## Files
- `swarm/done.py` (new) — task hash + git-trailer ledger.
- `swarm/flow.py` — commit trailers, queue/resume filtering, held-run approval, progress checkpoint + resume.
- `swarm/tui.py` — approve held run from `a`.
- `swarm/run.sh`, `Makefile` — approval path semantics (no new flag required).
- `swarm/tests/test_done.py`, `test_approval_resume.py`, `test_progress.py`, plus real-git cases in `test_autoloop.py`.
- `swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`, `changelog.md`.

## Status model
No new terminal status is required:
- held run → `awaiting_approval` (unchanged); approval success rewrites the same run to `green`, failure leaves it held with `approval_error`.
- checkpoint resume is a property of a normal run (`resumed_from_step`), not a status.
- existing non-green statuses (`merge_failed`, `push_failed`, …) still stop the loop.

## Risks / Open Questions
- **Task hash scope.** It covers id + brief + AC refs, not the whole spec/plan. A spec edit alone reopens nothing; a changed task does. This is a deliberate trade-off (reopening every green task on any spec edit would cause mass reruns).
- **Git history is the ledger.** Rewriting/deleting merged history loses done records; dirty/reset worktrees fail open and may rerun tasks. That is safer than silently skipping work.
- **Held-run drift.** Any new in-scope edit between hold and approval refuses approval; the human can rerun the task. Out-of-scope human edits are ignored (same run-delta rule as 012).
- **Checkpoint validity.** File hashes catch most divergence; gates/reviewer always rerun, so a resumed run cannot be greener than a fresh one.
- **Concurrency.** Still a single pilot + repo lock; checkpoints are per run dir and never shared across concurrent runs.
