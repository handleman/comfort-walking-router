# 015 Dark-Factory Economics — Plan

Status: proposed. References `specs/015-dark-factory-economics/spec.md` AC-1–AC-12. Builds on 012/013; keeps the `Flow` shape (planner → micro-step coders → QA → gates → branch/merge → next task), the run-delta/scope/secret guards, and the rule that the swarm never edits `specs/`.

Control plane: add `015-dark-factory-economics` to `HARNESS_SPECS` (`swarm/flow.py`) so the queue never picks these tasks up. They are executed explicitly.

## Approach

### 1. QA owns the gates; the harness owns the evidence (AC-1, AC-2)
Today green comes from `flow._run_gates()`, and the coder can also run gates after `BLOCKED`. Both change.

- `swarm/tools_guarded.py`
  - `ShellTool(allow_gates=False)` is the only construction used by coder-side crews (step, fix, senior). Remove the post-`BLOCKED` unlock.
  - Add execution logging: every run appends one line to `<run>/shell_log.jsonl`
    ```json
    {"ts":"…","agent":"QA Gatekeeper","argv":["pytest","-q"],"exit":0,
     "duration_ms":241,"changed_after":"<sha256 of in-scope delta>","tail":"…≤4000 chars"}
    ```
    The tool needs `run_dir` + `agent_role` (constructor args) and an append lock (thread-safe, `O_APPEND`). Writes go under `swarm/runs/<id>/`, which is outside coder scope and behind the secret/path guard.
- `swarm/flow.py`
  - Replace `_run_gates(changed)` with `_gate_evidence(changed)`:
    1. read `shell_log.jsonl`;
    2. for every command in `gate_commands()`, take the newest entry with `agent == reviewer` and `changed_after == hash_paths(in_scope)` at save time;
    3. require `exit == 0` for all of them;
    4. keep the flow-computed `scope` gate (run-delta scope check is not a shell command);
    5. missing/stale entries → `reason_code = "qa_gate_missing"`, and the flow asks QA for one more round before giving up.
  - `SWARM_TRUST_QA_EVIDENCE=1` (default) uses the evidence path; `=0` restores "flow re-runs gates" as a fallback for debugging. Green still requires parsed `PASS`, ≥1 in-scope change, and the scope gate (012 AC-4/AC-6 unchanged otherwise).

### 2. QA report → coder fix rounds (AC-3, AC-4)
- `swarm/crew.py`
  - Delete `VERIFY_RULE` / `MAX_FIX_VERIFY_CYCLES` (the coder no longer self-verifies).
  - `build_fix_crew` becomes **coder only**; QA is invoked by the flow between rounds via the existing `build_review_crew`.
  - New `qa_report(transcript, gates) -> dict` helper (or `swarm/evidence.py`): parses the QA output into
    `{"gates":[{"command","exit","tail"}], "changed_files":[…], "reason":"…", "verdict":"blocked"}`,
    with bounded tails (≤120 lines / 6000 chars per gate). Store as `run.json.qa_report`.
  - The fix prompt embeds that report verbatim: *"QA ran these gates; here are the exit codes and failure output. Investigate from this evidence — you do not run gates."*
- `swarm/flow.py`
  - Loop: coder fix (no gates) → `build_review_crew` (QA runs gates, appends evidence, returns report) → `_gate_evidence` → repeat while not green, `fix_rounds < 3`.
  - Stop immediately when evidence is green **and** QA says `PASS`; otherwise senior escalation gets the last report.
  - Record per round: model, qa report, gate evidence snapshot.

### 3. Paid for non-trivial, local for trivial (AC-5)
- New `swarm/routing.py`:
  - `classify_step(task, step, attempt) -> Route(kind: "paid"|"local", reason: str)`.
  - Non-trivial: edits an existing file; names >1 file; frontend/type-checked path (`frontend/`, `.svelte`, `.ts`, `.tsx`, `.css`); mentions logic/tests/API/DB/async/error-handling; retry after any failure. Trivial: create one new ≤40-line file, or a single import/constant/docstring change.
  - Ambiguous → `paid` (decision D2). Kill switch `SWARM_PAID_ALWAYS=1` and `SWARM_LOCAL_FIRST=0`.
- `swarm/crew.py`: `build_step_crew(..., model_kind)` picks `coder_llm()` or the local coder; step prompt states the route is recorded.
- `swarm/flow.py`: if a `local` step contributes to a red gate or a QA `BLOCKED`, re-run **that step** once with `paid`, record `escalated_from_local`.
- `run.json.steps[]` gains `{index, model, routing_reason, tokens, cost}`.

### 4. Attributable, capped spend (AC-6)
- `swarm/usage.py` / `swarm/flow.py`: wrap each kickoff, diff CrewAI `token_usage`, attribute to `(role, step)`; prices from the existing table; unknown price → `None` (never a fake number).
- `run.json.usage` gains `by_role` and `by_step`; `cost_note` explains which model dominated.
- Per-task budget: `SWARM_MAX_COST_PER_TASK` (default 0.05) and `SWARM_MAX_SECONDS_PER_TASK` (default 900), checked at step and round boundaries. On breach: `budget_exhausted` with `budget_task=<spec>/<task>`, queue advances.
- `make swarm-report` → `swarm/report.py`: cost per green task, tokens per role, fix-round rate, stop reasons, p50/p90 wall clock, gate wall time.

### 5. Never redo completed work (AC-7)
- `swarm/flow.py`: on `dev_attempts > 1`, keep `resume_from` from the checkpoint/first failing step instead of resetting to 0; re-run only that step and later ones.
- Checkpoint validation: on hash mismatch with matching plan hash, resume at `completed - 1` (redo the last step) rather than `0`; full restart only when `plan_hash`/`steps` differ.
- `run.json.recovery` records `checkpoint`, `last_step`, or `restart` with the reason.

### 6. Classified failures (AC-8)
- `swarm/flow.py`: `failure_signature(step, error)` (normalize paths/line numbers) → if already attempted on the same model, skip that model and escalate.
- Provider classifier: `_classify_provider_error(exc)` → `retryable` (429/5xx/timeout/empty) | `config` (HTML body, 404 HTML, 401/403, invalid base URL) | `unknown`.
  - `config` → status `config_error`, printed with the offending `SWARM_*_MODEL`/base URL; no retries.
  - `retryable` → existing backoff/fallback path, one extra rotate.

### 7. Unattended queue (AC-9)
- New `swarm/supervise.py` + `make swarm-supervise`:
  - run `./swarm/run.sh --resume` as a child; read the newest `run.json`;
  - retryable outcomes → restart with exponential backoff (10s→5min cap), `attempts[spec/task] += 1`, cap 3;
  - exhausted/unrecoverable → write `swarm/runs/retry_later.json` for that task and continue with the next runnable task;
  - stop on `config_error`, empty queue (all runnable tasks done), run budget, or `swarm/STOP` file.
- `retry_later` is a queue-side marker, not a run status; the dashboard shows it.

### 8. Hygiene and verification honesty (AC-10, AC-11)
- Out-of-scope writes: `Repository` tools already refuse them; if a write slips through (e.g. via shell), `save_run` restores those paths (`git checkout --`), records `out_of_scope_reverted`, continues.
- Unrelated dirty in-scope paths: `git stash push -- <paths>` at run start, restore in `finally` (also on signals), record `stashed`/`restored`. `SWARM_STASH_UNRELATED=0` disables.
- Preflight self-heal (`SWARM_SELF_HEAL=1`): `ollama create` a missing `swarm-qa`/`swarm-coder`, bootstrap `.venv` via the Makefile target, `npm ci` when `frontend/node_modules` is missing. Auth/base-URL failures stay terminal.
- DB tests: `SWARM_DB_MODE=sqlite` (default) provisions an ephemeral SQLite `DATABASE_URL` under the run dir so `tests/test_*.py` DB cases execute; `postgres` uses `DATABASE_URL` if set. Anything still unexecuted → `run.json.skipped_ac` + QA note; the task may go green only with that field populated.

### 9. Surfaces and docs (AC-12)
- `swarm/tui.py`: per-task cost, per-step model + routing reason, `qa_report` presence, stop class.
- `swarm/README.md`: ownership table (QA runs gates, flow reads evidence), report contract, budgets, `config_error`/`retry_later`/`qa_gate_missing`, supervisor, self-heal, stash.
- `AGENTS.md` (state + commands), `docs/roadmap.md`, `changelog.md`.

## Rollout order

1. **T7 first** (resume): orthogonal, biggest single $ win, no ownership change.
2. **T1 → T2 → T3 → T4** (ownership + evidence + report): one coherent change; land together so green never depends on the flow re-running gates in an intermediate state.
3. **T5, T6** (routing + money): needs T2's per-execution data to verify savings.
4. **T8, T9, T10, T11** (resilience/hygiene): independently shippable.
5. **T12** (docs/dashboard).

## Files

- `swarm/tools_guarded.py` — gate policy + `shell_log.jsonl` evidence.
- `swarm/crew.py` — remove self-verify, coder-only fix crew, QA report prompt, model routing.
- `swarm/flow.py` — evidence-based green, QA↔coder rounds, per-task budgets, resume, provider classifier, `HARNESS_SPECS`.
- `swarm/routing.py` (new) — trivial/non-trivial classifier.
- `swarm/evidence.py` (new) — shell log reader, QA report parser, failure signatures.
- `swarm/supervise.py` (new) — unattended queue supervisor.
- `swarm/report.py` (new) + `Makefile` — `make swarm-report`, `make swarm-supervise`.
- `swarm/tui.py` — cost/model/report/stop-class surfaces.
- `swarm/tests/` — evidence (fake logs), routing, resume, provider classifier, supervisor (fake `run.sh`), report, stash/revert.
- Docs: `swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`, `changelog.md`.

## Risks / Open Questions

- **Evidence is now the source of truth.** Mitigated by: the log is written by harness code (never the model), lives outside coder scope, and is hash-pinned (`changed_after`). `SWARM_TRUST_QA_EVIDENCE=0` restores the 012 behaviour if a regression appears.
- **QA must actually run every gate.** If it skips one, green becomes impossible rather than falsely green (`qa_gate_missing`) — the safe direction, but it can burn a round. The QA prompt enumerates the commands explicitly.
- **Routing misclassification.** Wrong "trivial" costs a red gate + one paid retry; wrong "paid" costs cents. Logged per step so the classifier can be tuned from real data.
- **SQLite is not Postgres.** DB tests that rely on Postgres semantics must set `SWARM_DB_MODE=postgres`; otherwise they are reported in `skipped_ac` rather than silently passing.
- **Supervisor loops.** Attempt caps per task, exponential backoff, budget-aware stop, and a `swarm/STOP` kill file.
- **Stash safety.** Only in-scope paths, always restored in `finally`/signal handlers; the stash name is recorded in `run.json` so a crash is recoverable by hand.
- **No parallel workers yet.** Deferred on purpose: the money work here is sequential; parallelism changes the lock model and deserves its own spec.
