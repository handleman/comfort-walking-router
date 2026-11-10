# 016 Conflict Recovery — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [x] T1 (AC-1, AC-5): resolve a failed `--no-ff` merge with one resolver crew.
  `_commit_changes(..., resolver=...)` keeps the merge state, hands
  `_unmerged_paths()` to `SwarmFlow._resolve_conflict`, and aborts if the
  attempt is not accepted. Evidence: `swarm/flow.py`, `swarm/tests/test_conflict.py`.
- [x] T2 (AC-2): deterministic acceptance — `conflict_markers()` must be empty and
  every `gate_commands()` argv must exit 0 before `git add` + `git commit`;
  otherwise `git merge --abort` and `merge_failed` with `autocommit.conflict`.
  Evidence: `swarm/tests/test_conflict.py::test_acceptance_requires_markers_gone_and_gates_green`.
- [x] T3 (AC-3): one role, no gate tool. `build_conflict_crew()` uses read/edit
  only; `conflict_llm()` defaults to `SWARM_CODER_MODEL`, overridable with
  `SWARM_CONFLICT_MODEL`, per-role fallbacks applied; `SWARM_CONFLICT_CREW=0`
  disables. Evidence: `swarm/crew.py`, `swarm/llms.py`, tests.
- [x] T4 (AC-4): usage under role `conflict` + `autocommit.conflict/merge`
  evidence in `run.json`. Evidence: `_resolve_conflict` / `_commit_changes`.
- [x] T5 (AC-6): stash-pop conflicts stay deterministic (no crew). Evidence:
  preflight `worktree` check + `stash_conflict` in `run.json`.
- [x] T6 (AC-7): stash lifecycle with no human step. `swarm/stashes.py` lists,
  archives (`refs/swarm/archive/<stamp>-<sha>` + `orphan_stashes.json`), sweeps
  orphaned `swarm-*` stashes at kickoff, and archives a conflicted restore's
  stash (`stash_conflict_ref`); non-`swarm-*` stashes are never selected.
  `SWARM_ARCHIVE_STASHES=0` disables. Evidence: `swarm/tests/test_stashes.py`
  (real repos: refs resolvable, user stash untouched, `UU` cleared).

Known gaps (follow-ups, not blocking): resolver runs are not budget-gated
beyond the run budget; a conflict in an out-of-scope path fails the attempt
(tools enforce `DEFAULT_SCOPE`) and stays `merge_failed` by design.
