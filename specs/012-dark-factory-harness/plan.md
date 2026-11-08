# 012 Dark-Factory Harness — Plan

References `specs/012-dark-factory-harness/spec.md` AC-1–AC-10. Phase 0 only: make green trustworthy and the loop safe before adding autonomy features.

## Approach
Keep the 009 shape (`Flow` → planner → micro-step coders → reviewer → gates → commit → next task). Add guards at the boundaries where the audit found lies:

1. **Snapshot before work.** `SwarmFlow` records a SHA-1 map of every path currently reported by `git status` *before* the first LLM call. A later snapshot difference is the **run delta**. Gates, vacancy, and autocommit consume the delta, so pre-existing human edits are invisible to the run.
2. **Guard at the tool.** Scope and secret checks live in `tools_guarded.py`, not only in the prompt. Edit/Create resolve + jail + scope-check every write. Shell parses argv (`shlex`, `shell=False`) and validates each command family. File reads resolve inside the repo (or an explicit test `base_dir`) and reject secret paths.
3. **One truth for green.** `gate` = all gates `0` **and** reviewer verdict `PASS` **and** non-empty in-scope run delta **and** (approval if required) **and** commit+push success. Anything else is an explicit non-green status. Cached plans get the same vacancy check.
4. **Plan cache = source content.** Cache files start with `<!-- plan-source: <sha256> -->`; a mismatch is treated as no cache. `parse_steps` no longer truncates; `steps_usable` enforces `1..MAX_STEPS` and sane step lengths.
5. **Single writer.** A `flock` on `swarm/runs/.lock` plus a PID file prevents concurrent pilots. Run ids append the PID + a short random suffix. Signal handlers mark the flow interrupted and persist `run.json`.
6. **Approval is explicit.** Default remains autonomous. `SWARM_REQUIRE_APPROVAL=1` / `--require-approval` holds a green run as `awaiting_approval` until the run dir or task ledger contains approval. `a` in the TUI and `--approve` write the ledger.

## Steps
1. (AC-1, AC-6) Add `snapshot_worktree`, `run_delta`, `in_scope`, `resolve_scope` to `swarm/tools_guarded.py`; make `scope_violations` exact-aware and secret-aware. Change `_commit_changes` to accept explicit paths and return `ok`. Capture the baseline in `SwarmFlow.__init__`; use the delta in `_run_gates`, vacancy, and commit.
2. (AC-2, AC-3) Rewrite `ShellTool`: `shlex.split`, `shell=False`, metacharacter rejection, per-command validators (`pytest`, `ruff check`, `mypy`, `git`, `ls`, `cat`, `grep`, `npm --prefix frontend`), secret/path guards. Add the same guard to `TrimmedFileReadTool`. Scope-check `EditTool`/`CreateTool`.
3. (AC-4) Add `reviewer_verdict` parsing; store it on state. Update `gate` to require `PASS`. Apply the vacancy guard to every green run (cached or fresh) using the run delta. Record `review_verdict` + notes in `run.json`.
4. (AC-5) Hash `spec.md`/`plan.md`/`tasks.md` into `plan_source_hash`; read/write a header in the cache. Reject stale caches. Replace silent `MAX_STEPS` truncation with `steps_usable` validation and normal replan failure.
5. (AC-6) Make `save_run` map commit/push failures to `commit_failed`/`push_failed`. Do not report green unless `_commit_changes(...).ok`.
6. (AC-7) Add `RunLock` (`flock`), PID file, unique run ids, and `SIGTERM`/`SIGINT` handlers that persist `interrupted` and release resources. Use the PID file in `swarm/stop.sh`.
7. (AC-8) Generate `SCOPE_RULE` from `DEFAULT_SCOPE`; add `_coder_role`/stack hints to coder, fix, and senior prompts. Remove dead `build_crew`/`build_exec_crew` prompts so there is one prompt source.
8. (AC-9) Add `require_approval` to `SwarmFlow`/`run_tasks`/CLI. Add `approval_path`, `_approval_granted`, `--approve`. TUI `a` writes `approved.json` + ledger. Green without approval → `awaiting_approval`, no commit.
9. (AC-10) Extend `run.json`: `brief`, `ac_refs`, `changed_files`, `review_verdict`, `approval`, `autocommit`, `evidence`.
10. Tests + docs: add regression tests for every guard; update `swarm/README.md`, `AGENTS.md`, `changelog.md`; add `012-dark-factory-harness` to `HARNESS_SPECS` so the swarm never implements its own control plane.

## Files
- `swarm/tools_guarded.py` — scope/secret guards, argv shell, run-delta helpers.
- `swarm/flow.py` — baseline, truthful gate, plan hash, lock/PID/signals, approval, commit coupling, evidence.
- `swarm/crew.py` — scope rule parity, role-aware prompts, step validation, dead-code removal.
- `swarm/tui.py` — approval ledger on `a`.
- `swarm/run.sh`, `swarm/stop.sh` — approval flag pass-through, PID-based stop.
- `swarm/tests/test_autoloop.py`, `test_tools_guarded.py`, `test_trimmed_read.py`, `test_create_tool.py`, `test_steps.py`, `test_scope.py` — regressions.
- `swarm/README.md`, `AGENTS.md`, `changelog.md` — behavior and commands.

## Status model
`green` only when every condition passes. Non-green is explicit:
`needs_human` (gates red, reviewer blocked/unknown, vacancy, approval missing when not configured), `awaiting_approval`, `commit_failed`, `push_failed`, `merge_failed`, `crew_error`, `quota_exhausted`, `budget_exhausted`, `interrupted`, `preflight_failed`.

## Phase 1 (T11–T16, implemented 2026-11-08)
- **Usage/cost (T11).** `_kickoff` folds `CrewOutput.token_usage` into `SwarmState` (prompt/completion/cached/total, LLM calls, models). `swarm/usage.py` prices the run: local + `:free` = `0.0`, one known paid model = estimate, unknown/multiple paid = `null`. `run.json` gains `usage` with start/finish/duration; the TUI renders tokens/cost instead of `cost=$0`.
- **Budgets (T14).** `SWARM_MAX_TOKENS`/`SWARM_MAX_COST_USD`/`SWARM_MAX_RUNTIME_SECONDS` are checked after every kickoff; exceeding one raises `_BudgetExhausted` → `budget_exhausted` + `budget_note`. `0` disables a limit.
- **Resilience (T13).** `_kickoff` takes a crew *builder* so a step can be rebuilt. Transient 429/timeout/5xx retry with 1s→8s backoff (3 attempts). A daily-quota error calls `activate_fallbacks()` and retries once with `SWARM_<ROLE>_FALLBACK_MODEL` (local Qwen default; senior prefers cheap Zen when paid is allowed), then `quota_exhausted`.
- **Lifecycle (T15).** `SwarmListener` records `(event, handler)` pairs; `teardown()` calls `crewai_event_bus.off` per flow (the queue object stays for the TUI). Tail mode seeks a byte offset and buffers partial lines.
- **Preflight (T12).** `swarm/preflight.py` validates roles/keys/Ollama/cloud ids/venvs/gates before the first LLM call; `preflight_failed` stops the run.
- **CI (T16).** `.github/workflows/ci.yml`: app gates, harness tests, frontend check/build, and a post-merge smoke job on `main`.

Phase 1 is complete (T11–T18). **T17** sandbox verified with Colima: image build, in-container tests,
OpenRouter/Ollama reachability, repo-only mount with `.env` masked. **T18**: each green task commits on
`swarm/<spec>-<task>`, pushes it, `--no-ff` merges into the base branch, pushes the base, and rolls back
the local merge if that push fails (`SWARM_MERGE_MODE=direct` restores the old behavior).

## Risks / Open Questions
- **Run-delta baseline** uses changed-file hashes. A file edited and then restored to its baseline hash is correctly “unchanged”; a file already dirty and further edited is correctly attributed to the run.
- **Root vs harness venv**: gates should use the app `.venv` when present, then fall back to `swarm/.venv`. `ShellTool` prepends both bins.
- **Approval timing**: the TUI can approve a live run before it reaches commit; `--approve` grants for the next run. Re-running an `awaiting_approval` task is still the fallback, acceptable for Phase 0.
- **Conservative vacancy**: a cached-plan retry that genuinely needs no edits becomes `needs_human`. That is intentional (no false greens); a human can mark the task done.
- **Sandboxing** is still process-level, not container-level. Path/secret guards reduce blast radius but do not replace the later container sandbox.
