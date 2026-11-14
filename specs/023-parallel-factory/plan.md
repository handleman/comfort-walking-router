# 023 Parallel Factory — Plan

Status: implemented (phase 1). References `specs/023-parallel-factory/spec.md`
AC-1–AC-6.

## Approach

Reuse the worktree mechanics from 020 T7 and keep the integration path boring:
workers are read-only with respect to the main tree, and the coordinator applies
one verified delta at a time.

```
T1  run_worker: worktree + harness copy + flow --no-commit
      │
      ├─ T2  independence grouping (brief paths)
      │
      ├─ T3  integrate: apply-check → full gates on main → commit/push
      │        │
      │        └─ T4  conflict/gate/commit rollback (task stays open)
      │
      └─ T5  run_batch: N workers, results queue, serial integration
               │
               └─ T6  CLI + measurement + docs
```

## T1 — worker

`parallel.run_worker` reuses `live.copy_harness`, `live.link_venvs`,
`live.fill_from_dotenv` and `live._run_dir`. It runs the flow with
`--no-commit`, reads the worktree's `run.json`, and extracts the
**scope-filtered** changed files (app/frontend/tests/contracts/requirements/
pyproject/.gitignore) and a binary diff against the worker's base. The worktree
is removed on green; a red worktree is kept for inspection.

## T2 — independence

`prompts.brief_paths` per task; tasks sharing a path go to different groups. A
group is mutually independent. Phase 1 takes up to `SWARM_WORKERS` tasks from
the first group, so it never combines conflicting briefs.

## T3 — integration

`parallel.integrate`:
1. `git apply --check --binary` → `conflict` if it does not apply;
2. `git apply --binary`;
3. run the full `gate_commands()` on the main tree;
4. `git apply -R` on any failure (leaves the tree clean);
5. `git add -A` + commit with the standard trailers, then a best-effort push.

The main-tree gates are the merge evidence; a worker's own green is a filter,
not the final word.

## T4 — rollback

`conflict`, `gates_failed` and `commit_failed` are explicit statuses. The task
stays unchecked; the serial queue picks it up again. No branch is created, so
the merge queue cannot see a half-integrated task.

## T5 — batch

`run_batch` starts one thread per chosen task, collects results in completion
order and integrates greens **on the calling thread**, so integration is
serialised by construction. A red worker is only recorded.

## T6 — CLI, measurement, docs

`python -m swarm.parallel --batch "007:T2,004:T2" --workers 2`;
`make swarm-parallel BATCH=… WORKERS=2`. The JSON result has per-task status and
`integrated`; the live comparison with the serial queue is recorded honestly
(not measured until a green baseline exists).

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Two workers share a file | brief-path grouping; phase 1 takes one group only |
| Main tree polluted by a worker | workers are `--no-commit` in their own worktree; the coordinator is the only writer |
| Patch applies but breaks a gate | the full suite runs on main; `git apply -R` on failure |
| Partial merge | no task branch, no merge queue involvement; a task is either integrated whole or rolled back |
| Cost doubles | workers are opt-in; the measurement compares cost per green |
| A worker hangs | the flow's wall budget and the worker timeout bound it |
