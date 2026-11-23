# 051 Acceptance Artifacts Commit — Tasks

Each task maps to one acceptance criterion.

- [x] T1 (AC-1): `swarm/acceptance.py` — `_commit_artifacts(repo_root, paths, subject, log)` stages only the given artifact paths, commits, pushes best-effort (120 s timeouts, never raises).
- [x] T2 (AC-2): only `write_report()`'s `<spec>/acceptance.md` and the `<spec>/tasks.md` touched by `queue_fix_tasks` are staged (tracked in `artifacts`).
- [x] T3 (AC-3): `git diff --cached --quiet` guard — a second pass with no change makes no empty commit.
- [x] T4 (AC-4): a failing add/commit/push is logged and the verdict is still returned.
- [x] T5 (AC-5): `_should_commit(commit, env)` — `commit=False` (held run) or `SWARM_ACCEPT_COMMIT=0` disables it; `run()` takes `commit: bool | None`.
- [x] T6 (AC-6): flow per-feature hook passes `commit=True` (it only runs after a committed green); supervisor/CLI use the default; tests for the helper + switch.
- [x] T7 (AC-6): `pytest swarm/tests/` green (783), `ruff check swarm/`, `mypy app tests` clean.
