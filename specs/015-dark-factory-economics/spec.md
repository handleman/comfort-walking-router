# 015 Dark-Factory Economics — Spec

**Status: implemented 2026-11-09 (T1–T12)** — see `tasks.md` for evidence.

Control-plane spec: it changes `swarm/` and must be added to `HARNESS_SPECS` (like 009/012/013), so the queue never tries to implement it.

## What / Why

The harness works but it is neither price-optimal nor fully autonomous. Measured across the 58 runs in `swarm/runs/`:

| Signal | Value |
| --- | --- |
| Green | 22 |
| Never finished (killed/restarted) | 20 |
| `crew_error` / `needs_human` / `preflight_failed` | 7 / 8 / 1 |
| Measured spend | $0.317 total, $0.304 of it on the 22 green tasks |
| Median green task | ~95k tokens, ≈$0.012, 2–7 min |
| Worst green task (`004-T4`) | 768k tokens, **$0.115 = 38% of all green spend** (fix=5, dev=3) |
| Silently unverified | 21 app tests skip without `DATABASE_URL` |

Four root causes:

1. **Work is redone instead of resumed.** A dev retry resets `resume_from = 0`, so a failing task pays for every micro-step up to `DEV_ATTEMPTS` (3) times. `004-T4` is three full passes.
2. **Every step re-sends boilerplate.** A fresh crew per micro-step re-sends role, backstory, stack hint, tool schemas, and scope rules (≈6–8k input tokens) on a paid model.
3. **Gates run redundantly and the flow, not QA, decides.** QA runs gates, the flow re-runs them, the fix crew's QA runs them again. Meanwhile the coder's post-`BLOCKED` unlock duplicates verification the flow already does.
4. **Stops are not classified.** 20 runs never finished because nothing restarts them; 429/empty-response/HTML-404 errors are all "crew_error"; unprovisioned DB tests make green look stronger than it is.

Nothing here needs a better model. It needs owned evidence, cheaper routing, and deterministic recovery.

## Decisions (locked)

- **D1 — QA is the only gate executor.** The coder never runs gates, in any phase (development, fix round, senior escalation). QA runs `SWARM_GATE_COMMANDS` and returns a **comprehensive report** to the coder: for every command, the exact argv, the exit code, and the captured error output (failing test names, linter/mypy/type-check lines), plus the changed-file list. That report is the coder's starting point for investigation.
- **D2 — Paid coder for anything non-trivial.** The local coder is a cost optimisation for trivial steps only (new small file, single import/config/doc line). Everything else uses the paid coder. Ambiguity resolves to paid. A trivial step that turns red is immediately retried with the paid coder.

Both decisions preserve the 012 invariant *truthful green*: see AC-2, which moves green's source of truth from "the flow re-runs the gates" to "the harness records what QA actually executed".

## Scope

- In scope:
  - `swarm/tools_guarded.py`: QA-only gate policy for every coder crew; every shell execution appended to a per-run evidence log with agent role, argv, exit code, duration, and output tail.
  - `swarm/crew.py`: remove the coder self-verify cycle; QA report task/contract; step classifier hint; fix crew becomes coder-only.
  - `swarm/flow.py`: green from harness-recorded QA evidence; QA↔coder fix rounds (3); resume at the failing step; per-task budgets; per-role/per-step usage; provider-error classification; `retry_later` status.
  - `swarm/routing.py` (new): deterministic trivial/non-trivial step classifier and model choice.
  - `swarm/supervise.py` (new) + `Makefile`: unattended queue supervisor with attempt caps and backoff.
  - `swarm/evidence.py` or `swarm/flow.py` helpers: gate evidence reader, QA report builder, failure-signature cache.
  - Hygiene: auto-revert out-of-scope writes, stash/restore unrelated dirty files, preflight self-heal.
  - `docs/reports`: `make swarm-report`.
  - Tests and docs (`swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`, `changelog.md`).
- Non-goals:
  - Parallel workers / multiple worktrees (deferred; the merge queue already supports it).
  - Changing the model set or adding paid QA; QA stays `ollama/swarm-qa:latest` (64k) with the existing free verdict fallback.
  - PR creation, branch protection, remote CI.
  - Editing `specs/` from the swarm.
  - Rewriting the 012 safety model (scope, secrets, run-delta, commit/push coupling). Only the *gate executor* changes.

## Acceptance Criteria

- [x] AC-1: **Only QA runs gates.** Every coder-side crew (micro-step, fix, senior) is constructed with `ShellTool(allow_gates=False)`; `pytest`, `ruff`, `mypy`, each `SWARM_GATE_COMMANDS` entry, and `npm run check|lint|test` all return `BLOCKED: gates are QA-only`. No coder prompt offers a self-verify cycle; the only agent that may execute a gate is the reviewer. Read-only inspection (`git status|diff|log`, `ls`, `cat`, `grep`) and `npm run build` remain available.
- [x] AC-2: **Harness-recorded gate evidence (truthful green).** Every `ShellTool` execution appends one JSON line to `<run>/shell_log.jsonl` (`agent`, `argv`, `exit`, `duration_ms`, `started_at`, `changed_after` = in-scope content hash at execution). Green requires, for every command in `SWARM_GATE_COMMANDS`, a QA execution whose exit is `0` and whose `changed_after` equals the current in-scope hash, plus the flow-computed `scope` gate, a parsed `VERDICT: PASS`, and ≥1 in-scope change by this run. Model text is never the source of an exit code; a missing or stale QA run yields `qa_gate_missing` (not green) and triggers one more QA round.
- [x] AC-3: **Comprehensive QA report.** `run.json.qa_report` and the coder's fix prompt contain, per gate: exact argv, exit code, and a bounded output tail (default ≤120 lines / ≤6000 chars per gate) including failing test node ids, linter rule ids, and mypy error lines; plus the in-scope changed-file list and QA's one-line reason for `BLOCKED`. The coder must be able to start investigating without re-running anything.
- [x] AC-4: **Bounded QA↔coder fix rounds.** A fix round is: QA report → coder fix (no gates) → QA re-verification (runs gates, records evidence, new report). At most `MAX_FIX_ROUNDS = 3` rounds per dev attempt; the loop ends as soon as recorded evidence is green and QA says `PASS`, and otherwise hands to the senior escalation with the last report. `run.json` records `fix_rounds`, the model used per round, and the last report.
- [x] AC-5: **Paid for non-trivial, local for trivial.** `swarm/routing.py` classifies each micro-step deterministically: *non-trivial* when it edits an existing file, touches more than one file, touches a frontend/type-checked path, asks for logic/tests/API/DB work, or is a retry after a failure → paid coder. *Trivial* (new ≤40-line file, single import/constant/docstring line) → local coder. Ambiguous defaults to paid. A trivial step that lets a gate go red is re-run once with the paid coder. `run.json` records `model` and `routing_reason` per step.
- [x] AC-6: **Cost and time are attributable and capped.** `run.json.usage.by_role` and `usage.by_step` record prompt/completion tokens, model, and estimated cost per role and per step. `SWARM_MAX_COST_PER_TASK` / `SWARM_MAX_SECONDS_PER_TASK` (defaults $0.05 / 900s) stop a single task with `budget_exhausted` while the run budget stays separate. `make swarm-report` prints cost per green task, tokens per role, fix-round rate, stop reasons, and p50/p90 duration from `run.json` files.
- [x] AC-7: **Completed work is never re-executed.** A dev retry resumes at the first uncompleted/failed step using the stored `step_outputs` instead of resetting to step 1. A checkpoint whose hashes mismatch resumes at `completed - 1` (redo only the last step) when the plan hash and earlier steps still match; it restarts from 0 only when the plan itself changed. `run.json` records `resumed_from_step` and `recovery` for both cases.
- [x] AC-8: **Failures are classified, not retried blindly.** A failure-signature cache keyed on `(task, step, normalized error)` prevents retrying the same step on the same model twice; the second attempt escalates (paid/local swap or senior). Provider failures are classified: 429/5xx/timeout/empty → retry with backoff and the configured fallback; HTML/404/auth/base-URL/`Invalid response` → terminal `config_error` with the offending model/URL, no retry loop.
- [x] AC-9: **Unattended queue.** `make swarm-supervise` restarts the queue after retryable outcomes (`interrupted`, transient `crew_error`, `quota_exhausted`, `budget_exhausted` with headroom) with exponential backoff and a per-task attempt cap. Non-retryable outcomes mark the task `retry_later` and the queue advances to the next runnable task instead of blocking head-of-line. The supervisor stops on `config_error`, a green queue, or the run budget.
- [x] AC-10: **Hygiene is automatic.** Out-of-scope writes by the coder are reverted (paths restored, `run.json.out_of_scope_reverted` recorded) and the run continues; unrelated dirty in-scope files are stashed before the run and restored after (`SWARM_STASH_UNRELATED=1`, default on) instead of stopping as `needs_human`. With `SWARM_SELF_HEAL=1`, preflight rebuilds a missing `swarm-qa`/`swarm-coder` image, bootstraps a missing venv, and runs `npm ci` for missing `frontend/node_modules`; only genuine failures (bad key, unreachable provider) stop.
- [x] AC-11: **Green is never silently unverified.** When a task's tests are DB-backed and `DATABASE_URL` is configured, they execute (the harness passes it through; this repo uses Postgres/psycopg, so SQLite is not a substitute). If tests still skip, `run.json.skipped_ac` lists the task's AC refs and `verification_note` explains what is unexercised, so a green task touching persistence is never silently unverified.
- [x] AC-12: **Observable and documented.** The dashboard shows per-task cost, per-step model/routing reason, QA report availability, and the stop class; `swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`, and `changelog.md` describe the new ownership, budgets, statuses (`config_error`, `retry_later`, `qa_gate_missing`), and supervisor usage. `015-dark-factory-economics` is added to `HARNESS_SPECS`.

## Success measures

- Median cost per green task ≤ **$0.008** (from ≈$0.012) and the `004-T4` class (fix=5, dev=3) ≤ **$0.05** (from $0.115).
- Zero human interventions for retryable stops over a 10-task unattended batch; `needs_human` limited to scope/approval/ambiguity.
- No gate command executed by a coder in any run log; every green `run.json` has `qa_report` with one entry per configured gate.
- Completed steps re-executed after a retry: **0**.
