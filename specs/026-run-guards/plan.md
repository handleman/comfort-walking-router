# 026 Run Guards — Plan

Status: proposed. References `specs/026-run-guards/spec.md` AC-1–AC-11 and the
2026-11-14 lessons in `AGENTS.md` / `changelog.md`.

## Approach

Guards sit **around** the model phases, not inside them. Each is deterministic,
has an off switch, writes a typed reason code, and is cheaper than the phase it
replaces.

```
coder steps
   │
   ├─ T1 delta guard        empty? brief-named files touched?   → no_delta / delta_incomplete
   ├─ self-check (017)      static checks
   ├─ T4 correction guard   did a correction turn green→red?     → revert it + correction_reverted
   ├─ verifier (019)        fail-closed verdict, bounded repair
   ├─ QA (015)              fail-closed verdict (existing repair kept)
   └─ commit / merge queue

provider calls
   ├─ T5 quota breaker      N quota errors on one provider       → quota_exhausted
   ├─ T6 one retry layer    agents max_retry_limit=0
   └─ T7 cost fail-closed   per-model price, cost_unknown flag
```

Order matters: T1 and T4 are the cheapest and prevent the two most expensive
shapes; T5–T7 are provider-level; T8–T10 restore trust in green and the queue.

## T1 — delta guard (AC-1, AC-2)

New `swarm/guards.py`:

- `empty_delta(changed) -> bool`
- `missing_brief_files(brief, changed, repo_root) -> list[str]` using
  `prompts.brief_paths` minus paths that already existed before the run
  (`self._baseline`).
- Flow calls it right after the coding phase, **before** `_verify_phase`:
  `reason_code=no_delta` / `delta_incomplete`, `run.json.delta_guard` with
  `named`, `touched`, `missing`, `phase`.
- Off switch `SWARM_DELTA_GUARD=0`. Default on: it saved ~35 min in the observed
  runs and cannot make a green run red (it only stops an empty/absent delta).

## T2 — fail-closed judges (AC-3)

The verifier already re-asks once and stops (`019` fix, this session). Extract
the pattern into `guards.verdict_or_stop(parse, repair, label)` so QA and the
senior verdict path use the same rule:

- parse → `pass|blocked|unknown`;
- `unknown` → one repair (no tools), parse again;
- still `unknown` → typed stop with the output tail, never green.
- Reviewer path keeps its existing `_repair_verdict` order (reviewer → senior);
  the guard only decides the terminal case.

## T3 — correction regression guard (AC-4)

In `_verify_phase` after each `build_senior_step_crew` call:

- run `self_check` commands (static subset; already implemented) or, when the
  correction touched a `.svelte`/`.ts` file, at least `npm --prefix frontend run
  check`;
- compare to the pre-correction result (captured before the steps);
- if a green→red transition happened: `git checkout -- <files touched by that
  step>` (archive first, same as `_revert_out_of_scope`), record
  `verifier.correction_reverted` and break the correction loop, leaving the
  run to stop `needs_human`.
- Off switch `SWARM_CORRECTION_GUARD=0`.

## T4 — quota breaker and usable fallbacks (AC-5)

- `swarm/retry.py` already classifies `429 free-models-per-day` as `quota`.
- Count quota errors per run/provider in state; on the third, raise
  `_QuotaExhausted` regardless of which crew saw it (CrewAI may surface it as
  `agent_error`; the flow also inspects `crew_failed` text for the hint).
- `llms.fallback_model` returns `''` when nothing is callable; callers must then
  fail closed instead of falling back to the primary. Record
  `run.json.quota` = `{provider, errors, stopped}`.
- Preflight: a 1-token `llm.call("ok")` per configured role (skipped with
  `--offline`), reporting `quota/429` before the first real task.

## T5 — one retry authority (AC-6)

`swarm/crew.py` builds every `Agent` with `max_retry_limit=0`; the flow's
three attempts remain the only retry. Test: a counting fake LLM raises once and
is called exactly once per attempt.

## T6 — cost fail-closed (AC-7)

Per-model cost landed this session. Remaining:

- `estimate_cost` returning `None` sets `usage.cost_unknown = True` and a
  `budget_note` naming the unpriced model; a `/` in the dashboard shows
  `unknown` instead of `$0`.
- Test: paid planner + paid coder → numeric cost; unknown model → the flag and
  no silent pass of the cap.

## T7 — e2e evidence (AC-8)

- `evidence.py` gains `e2e_executions(run_dir)` reading `shell_log.jsonl` for
  `npm --prefix frontend exec playwright test` (agent `QA Gatekeeper` or
  `harness-fallback`).
- `run_crew` checks it only when `brief_paths` names a `frontend/e2e/*` file;
  green without it is `e2e_missing` (`SWARM_E2E_EVIDENCE=0` to disable).
- `Makefile`: `e2e` target = build frontend + `playwright test` from
  `frontend/` with the fixture env (the config fixes are already committed).
- Preflight: `frontend/node_modules/.bin/playwright` exists and
  `npx playwright --version` matches the installed browsers.

## T8 — readable config errors (AC-9)

- `_ConfigError` already carries text; ensure `run.json.error` is set from it in
  `save_run` and `human_log.txt` names the role and exception.
- Preflight builds planner/coder/reviewer/senior/verifier with the same flags the
  crews use (planner `allow_paid=True`, others follow `SWARM_ALLOW_PAID`).

## T9 — queue diagnostics (AC-10)

- `swarm/done.py` returns an entry plus a reason; `flow._open_task_ids` logs
  `open task <id>: <reason>` (reason ∈ `no ledger entry`, `spec hash changed`,
  `task hash changed`).
- `Makefile`/`swarm/record.py`: `make swarm-record SPEC=014 TASK=T11` writes the
  standard `Swarm-Task`/`Swarm-Task-Hash`/`Swarm-Spec-Hash` trailers for a
  manually completed task and records the ledger cache.

## T11 — wall budget is terminal (AC-12)

`bounded.run_bounded(fn, timeout: float | None)` — `None` is the only unbounded
mode; a zero/negative timeout means "already expired" and returns without
starting the call. The flow checks `remaining <= 0` before invoking a crew and
raises `_WallBudget`. This landed with the 007 overrun fix; the task here is the
regression test and the record.

## T10 — wiring and docs (AC-11)

- Add `026-run-guards` to `HARNESS_SPECS`.
- AGENTS lessons: the six shapes with the guard that now covers each.
- changelog entry; roadmap line; off-switch table in `swarm/README.md`.

## Risks / open questions

- **False positives in AC-2.** A brief can name an example path that must not be
  touched; the guard therefore stops (not fails) with the list, and
  `SWARM_DELTA_GUARD=0` restores the old path. Measure on the replay set before
  turning `delta_incomplete` from a stop into a gate.
- **Correction revert cost.** Reverting a correction that legitimately fixed
  something but tripped an unrelated red check could loop; bounded by one revert
  per round and `MAX_VERIFY_ROUNDS`.
- **E2E wall time.** A Playwright run adds ~30 s per task; only tasks whose brief
  names e2e pay it.
- **Quota counting under concurrency.** With `SWARM_VERIFY_CONCURRENT` two crews
  can see the same wall; the counter must be locked and the stop idempotent.
