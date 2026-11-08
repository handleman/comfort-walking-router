# 012 Dark-Factory Harness — Tasks

## Phase 0 — trust & safety (this change)
- [x] T1 (AC-1): Capture a worktree hash snapshot in `SwarmFlow.__init__`; use the run delta for gates, vacancy, and autocommit so pre-existing human edits are ignored.
- [x] T2 (AC-2): Make `Repo Edit`/`Repo Create` reject out-of-scope, absolute, `..`, symlink-escape, and secret paths; add tests.
- [x] T3 (AC-3): Replace `ShellTool` with `shlex` + `shell=False` argv validation; deny metacharacters, `.env*`, absolute/`..` paths, `npm install`, and `pip`/`uv`; guard `TrimmedFileReadTool`; add tests.
- [x] T4 (AC-4): Parse the reviewer `PASS`/`BLOCKED` verdict, require `PASS` for green, and apply the vacancy guard to cached-plan runs too; record notes in `run.json`.
- [x] T5 (AC-5): Hash `spec.md`/`plan.md`/`tasks.md` into the plan cache header and invalidate on mismatch; reject zero/over-limit/malformed steps instead of truncating.
- [x] T6 (AC-6): Couple commit+push to green: `commit_failed`/`push_failed` are non-green; add only run-delta in-scope paths.
- [x] T7 (AC-7): Add a repo lock + PID file, unique run ids, and `SIGTERM`/`SIGINT` handlers that write an `interrupted` trace and release the lock.
- [x] T8 (AC-8): Generate `SCOPE_RULE` from `DEFAULT_SCOPE`; add role/stack-aware coder prompts; remove dead `build_crew`/`build_exec_crew` prompts.
- [x] T9 (AC-9): Honor `approved.json` + a task approval ledger; add `--require-approval`/`--approve` and make TUI `a` write the ledger; unapproved green → `awaiting_approval`.
- [x] T10 (AC-10): Record brief, `ac_refs`, changed files, gates, reviewer verdict, approval, and commit/push evidence in `run.json`.

Phase 0 evidence (2026-11-08): `make swarm-test` 73 passed, `make test` 4 passed, `make lint` clean, `make typecheck` clean, `npm run check` 0 errors; gate smoke `pytest -q`/`ruff check .`/`mypy app tests` all exit 0 through `Guarded Shell`.

## Phase 1 — observability & resilience (follow-up)
- [x] T11 (AC-10): Capture per-run tokens/cost/timestamps from crew usage metrics; remove the hardcoded `cost=$0` in the TUI.
- [x] T12 (AC-10): Add a preflight command that checks venvs, model keys, Ollama reachability, and gate binaries before the first LLM call.

Phase 1 evidence so far (2026-11-08): `swarm/preflight.py` + `make swarm-preflight` validate role ids, provider keys, Ollama pull, cloud model lists, both venvs, and `pytest`/`ruff`/`mypy`; `run_crew` runs it before the first LLM call and stops with `preflight_failed` (`SWARM_SKIP_PREFLIGHT=1` bypasses). `run.json` now carries `usage` (tokens, cached tokens, LLM calls, models, cost, start/finish/duration) with `$0` for local/`:free` and `null` for unknown paid rates; the TUI shows `tok=`/`cost=` and tail mode reads events.jsonl by byte offset. Budgets (`SWARM_MAX_TOKENS`/`SWARM_MAX_COST_USD`/`SWARM_MAX_RUNTIME_SECONDS`) stop with `budget_exhausted`; 429/timeout/5xx retry with 1s→8s backoff and switch to `SWARM_<ROLE>_FALLBACK_MODEL` (senior: cheap Zen when paid is allowed) before `quota_exhausted`. `SwarmListener.teardown()` unregisters handlers per flow. The Textual dashboard (ADR-011) shows the queue with per-task outcomes, models/fallback, token/cost/time budgets, gate exit codes, recent runs, and approval state. `.github/workflows/ci.yml` runs app + harness + frontend gates plus a post-merge smoke job. 148 harness tests, 4 app tests, ruff/mypy clean. Remaining: T17 (container sandbox), T18 (branch/merge queue).
- [x] T13 (AC-3): Add model fallback/backoff/retry feedback with quota-aware routing; wire the unused Zen fallback.
- [x] T14 (AC-7): Add per-run token/cost/time budgets that stop the loop with a `budget_exhausted` status.
- [x] T15 (AC-7): Tear down the CrewAI event listener after each flow; make the TUI tail incremental instead of re-reading `events.jsonl` every tick.
- [x] T16 (AC-6): Add CI workflows for app + harness gates and a post-merge smoke job.
- [ ] T17 (AC-2): Move the coder into a container/VM sandbox with an explicit mount allowlist.
  Sandbox config landed (`swarm/docker/Dockerfile`, `swarm/sandbox.sh`, `.dockerignore`, dry-run tests:
  repo is the only mount, caps dropped, SSH opt-in); **not verified** because this machine has no
  Docker daemon. Run `make swarm-sandbox` once Docker is available.
- [x] T18 (AC-6): Add branch-per-task + merge queue + rollback (replacing direct autocommit to the current branch).
