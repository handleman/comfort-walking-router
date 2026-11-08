# 012 Dark-Factory Harness — Spec

## What / Why
Turn the 009 pilot into a **lights-out (dark-factory) harness**: specs are the only input; the swarm plans, codes, verifies, repairs, commits, and advances on its own. Humans only handle exceptions (`needs_human`, quota, approval holds).

A 27-run audit of the 009 harness found trust and safety gaps that make autonomy unsafe:

- **False green**: the reviewer verdict was ignored, and the vacancy guard was skipped whenever a cached plan was reused.
- **Unsafe tools**: `ShellTool` used `shell=True` and allowed `cat .env`, absolute paths, `..`, and arbitrary `npm`; file reads were unguarded; `Repo Edit`/`Repo Create` were repo-jailed but not scope-aware.
- **Stale plans**: the plan cache key was only `spec-task`; spec edits reused old plans, and `MAX_STEPS=8` silently truncated work.
- **Lying status**: a failed `git push` still produced `status=green`; gates/commits considered every dirty worktree file, including human work.
- **No concurrency/signal safety**: two pilots could run at once, run ids collided within a second, and `SIGTERM` left no trace.
- **Dead approval key**: the TUI wrote `approved.json`, but the flow never read it.
- **Prompt drift**: `SCOPE_RULE` was hardcoded and omitted `tests/`; every task was described as “Python Scaffold Coder”, including frontend/TS tasks.

This spec defines **Phase 0 (trust & safety)**. Observability, model fallback, and budget work stay in Phase 1 tasks.

## Scope
- In scope:
  - `swarm/flow.py`: run-delta baseline, truthful green, commit/push coupling, plan hash, lock/PID/signals, approval, AC evidence.
  - `swarm/tools_guarded.py`: scope-aware Edit/Create, secret-safe read, argv-based ShellTool with per-command allowlists.
  - `swarm/crew.py`: `SCOPE_RULE` derived from `DEFAULT_SCOPE`, role-aware coder prompts, strict step validation.
  - `swarm/tui.py`: approval ledger written by `a`.
  - `swarm/run.sh`, `swarm/stop.sh`, `Makefile`, `swarm/README.md`, `AGENTS.md`, `changelog.md`.
  - `swarm/tests/`: regression tests for every Phase 0 guard.
- Out of scope (Phase 1+):
  - Token/cost/timestamp accounting, preflight, model fallback/backoff, budgets, listener teardown, incremental TUI tail.
  - Container/VM sandboxing, branch-per-task/merge queue/rollback, PR creation.
  - Auto-ticking spec checkboxes (the swarm still never edits `specs/`).

## Acceptance Criteria
- [x] AC-1: **Run delta.** Each run snapshots the changed-worktree file hashes before any LLM call. Gates, vacancy, and autocommit use only files changed by that run; unrelated human edits are neither gate failures nor committed.
- [x] AC-2: **Tool-level scope.** `Repo Edit` and `Repo Create` refuse paths outside `DEFAULT_SCOPE`/`SWARM_SCOPE`, absolute paths, `..`, symlink escapes, and secret-looking paths.
- [x] AC-3: **Secret-safe inspection.** `Guarded Shell` runs with `shell=False` + `shlex`, rejects shell metacharacters, absolute paths, `..`, `.env*`/key files, and allows only per-command forms (`pytest`, `ruff check`, `mypy`, `git status|diff|log`, `ls`, `cat`, `grep`, `npm --prefix frontend run check|build|test`). `pip`/`uv` stay blocked. File reads use the same secret/path guard.
- [x] AC-4: **Truthful green.** Green requires all gates `0`, a parsed reviewer `PASS` (unknown/`BLOCKED` → `needs_human`), and at least one in-scope file changed by this run — including cached-plan runs. Verdict + vacancy notes are recorded in `run.json`.
- [x] AC-5: **Plan integrity.** The plan cache records a content hash of `spec.md` + `plan.md` + `tasks.md`; a changed source invalidates the cache. Plans with zero, over-limit (`>MAX_STEPS`), or malformed steps fail loudly through the normal replan/`crew_error` path, never silent truncation.
- [x] AC-6: **Atomic green.** Commit and push are part of green. `git add`/`commit` failure → `commit_failed`; `push` failure → `push_failed`; neither leaves `status=green`. Only run-delta in-scope paths are added.
- [x] AC-7: **Single run + crash trace.** A repo-wide lock prevents concurrent pilots. Run directories include a unique suffix. `SIGTERM`/`SIGINT` writes an `interrupted` `run.json`, releases the lock, and removes the PID file.
- [x] AC-8: **Prompt parity.** `SCOPE_RULE` is generated from `DEFAULT_SCOPE` (including `tests/`). Coder role/backstory/step prompts are stack-aware (`Frontend Coder` for `frontend/`/Svelte/TS/npm work, test-oriented for test-only work).
- [x] AC-9: **Approval policy.** With `--require-approval`/`SWARM_REQUIRE_APPROVAL=1`, a green run without approval becomes `awaiting_approval` and is not committed. Approval is read from the run’s `approved.json` or a task-keyed ledger (`swarm/runs/approvals/<spec>-<task>.json`); the TUI `a` key and `--approve` write the ledger.
- [x] AC-10: **AC evidence.** `run.json` records the task brief, `ac_refs`, changed files, gate exit codes, reviewer verdict, and approval/commit/push outcome, so a human can audit any green task without replaying the logs.
