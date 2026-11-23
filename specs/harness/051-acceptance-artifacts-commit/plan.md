# 051 Acceptance Artifacts Commit — Plan

References `specs/harness/051-acceptance-artifacts-commit/spec.md` AC-1–AC-6.

## Approach

One helper and one call, inside `swarm/acceptance.py`, so both callers (flow
per-feature hook and supervisor drain) get it for free.

## Steps

1. `COMMIT_ENV = "SWARM_ACCEPT_COMMIT"`.
2. `_commit_artifacts(repo_root, paths, subject, log) -> dict[str,str]`:
   - keep only paths that exist; `git add -- <rel paths>` (relative to root),
   - `git diff --cached --quiet`: if clean, return `{}` (no empty commit),
   - `git commit -m <subject>`, then `git push` (best effort),
   - all subprocess calls `check=False`, 120 s timeout, errors logged not raised.
3. In `run()`: collect artifacts (`write_report(...)` return; `tasks_path` when
   `added`), compute the verdict, then call `_commit_artifacts` when enabled.
4. Tests: build a tmp git repo, write an `acceptance.md` + `tasks.md`, call the
   helper; assert the commit exists, only those paths are in it, a second call
   is a no-op, a bad path fails quietly, and the env switch disables it.
5. Verify: `make swarm-test`, `ruff`, `mypy app tests` green.

## Risks

| Risk | Mitigation |
| --- | --- |
| Committing mid-flow disturbs the task commit | Artifacts are staged by explicit path only; the task already merged before the hook runs |
| A push failure fails the acceptance | `push` is best effort; the verdict is returned regardless |
| Re-running the pass creates empty commits | `git diff --cached --quiet` guard |
| Dirty `tasks.md` still stashed by the next run | The commit removes it from the tree, so nothing to stash |

## Rollback

Delete the call + helper; `SWARM_ACCEPT_COMMIT=0` also disables at runtime.
