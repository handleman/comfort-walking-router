# Run guards (026)

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

### Run guards (026)

Deterministic checks that run **around** model phases. They exist because the
cheap answer is almost always available before a judge is paid:

- **Delta guard** (`run.json.delta_guard`, `SWARM_DELTA_GUARD=0` off): after the
  micro-steps and **before** the self-check/verifier/QA, an empty in-scope delta
  stops as `reason_code=no_delta`; a brief-named file that did not exist before
  the run and is still absent stops as `delta_incomplete` with the list. A named
  existing file that was not touched is recorded as `untouched` (a warning, not a
  stop — briefs name files for context too). Dotted code such as `route.waypoints`
  is not a path. This is what the two 014-T10 empty-delta runs (21 + 28 min,
  $0.18) needed.
- **Wall budget is terminal** (`SWARM_TASK_WALL_BUDGET`): `bounded.run_bounded`
  only treats `None` as unbounded; a zero/negative remaining budget refuses the
  call, and the flow raises `_WallBudget` before a crew. 007-T10 once ran 2.7 h
  past its 1800 s bound because a spent budget became a negative timeout, which
  the old code read as "no bound".
- **Per-model cost** (`run.json.usage.by_model`): each model's own tokens are
  priced. With a paid planner + paid coder the old aggregate returned `None`,
  which silently disabled `SWARM_MAX_COST_PER_TASK`; the default cap is **$1.00**
  per task (`SWARM_MAX_COST_PER_TASK`).
- **Journal after close** (`run.json.journal`): the run-end `save_run` listener
  runs after `_cleanup`; `fold` returns a `closed` view and `append`/
  `record_effect` are no-ops, so a terminal stop cannot crash the run record.
- **Judges fail closed** (`SWARM_JUDGE_FAIL_CLOSED=0` off): the verifier, QA and
  the senior path go through `guards.resolve_verdict` — parse, **one** bounded
  repair call, then a terminal stop. `run.json.judges[<kind>]` records the
  verdict, whether a repair ran and the raw tail. 014-T10 committed green because
  the verifier spent its turn on tool calls and an `unknown` verdict fell through
  as a pass. `review_note` names the terminal judge.
- **Corrections cannot regress the build** (`SWARM_CORRECTION_GUARD=0` off):
  before a verifier correction plan and after each `STEP n:` the harness runs the
  017 static checks (`harness-selfcheck` role, never QA evidence); a green→red
  transition reverts only that step's new paths (archived in
  `<run>/reverted/`), records `run.json.correction_reverted`, ends the loop and
  stops as `reason_code=correction_reverted`. 014-T11 appended a duplicate style
  block to `App.svelte` after the self-check had passed.
- **Quota is terminal** (`SWARM_QUOTA_BREAKER=0` off, `SWARM_QUOTA_LIMIT=3`):
  quota errors are counted **per provider** in `run.json.quota`; at the limit the
  run stops `quota_exhausted` instead of retrying a walled model. Fallbacks skip
  providers whose key is missing (`llms._callable`), and `make swarm-preflight`
  makes one 1-token call per role (`--offline` skips it). 014-T10 burned 54
  `429 free-models-per-day` errors and 20 minutes.
- **Cost is never silently unknown** (`run.json.usage.cost_unknown`): with two
  paid models the cost is a number; an unpriced paid model sets
  `cost_unknown: true`, names it in `unpriced_models` and in the budget note
  ("the dollar cap cannot fire"), and the dashboard prints "unknown" — never `$0`.
- **E2E evidence** (`SWARM_E2E_EVIDENCE=0` off): a task whose brief (or delta)
  names `frontend/e2e/*` is green only with a recorded Playwright execution at
  the current delta hash; otherwise `reason_code=e2e_missing` (a stale pass —
  from before the last fix round — is not evidence either). The check is
  satisfiable: QA's prompt names the exact commands and Guarded Shell allows them
  (`npm --prefix frontend run build`, then
  `npm --prefix frontend exec playwright test [e2e/x.spec.ts]`; no flags, so a
  model cannot narrow the suite, and coders are refused). `make e2e` is the
  operator's single entry point; preflight checks
  `frontend/node_modules/.bin/playwright` and the config. 010-T4 was green having
  touched only `helpers.ts`.
- **Config errors are readable** (`run.json.error`): every typed config failure
  writes its exception text, `human_log.txt` shows it as `error: …`, and
  preflight builds the crews' own factories (planner `allow_paid=True`, others
  follow `SWARM_ALLOW_PAID`) via `SWARM_PREFLIGHT_FACTORIES=0` to disable.
- **One retry authority** (`swarm/crew.py`): every `Agent` is built with
  `max_retry_limit=0`, so a provider outage costs the harness's 3 attempts, not
  20 nested calls.
- **The queue explains itself** (`run.json.queue_reasons`): queue selection logs
  `open task <spec>/<T>: <reason>` with `no ledger entry` / `missing trailer` /
  `task hash changed` / `spec hash changed`. `make swarm-record SPEC=014 TASK=T11`
  writes the standard trailers for work finished by hand (an empty commit plus
  the ledger cache) — `--dry-run` / `--no-commit` for inspection.
- **Delta completeness stays a stop, not a gate.** `delta_incomplete` is
  promoted to a gate only after the replay set agrees; the verifier still judges
  behaviour.
