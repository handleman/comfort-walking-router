# 026 Run Guards — Spec

Control-plane spec (added to `HARNESS_SPECS`): the queue never implements it.

## Problem

On 2026-11-14 the loop produced six expensive failure shapes that were not model
quality problems — each was a missing deterministic guard around a model phase:

1. **Empty delta.** Two `014-T10` runs (21 min, 28 min) ended with `changed: []`
   and then paid a verifier to name the missing files. `007-T10` and `014-T2`
   are the same shape: the module exists, nothing mounts it.
2. **Unknown verdict = pass.** `014-T10` attempt 1 committed green with three
   missing deliverables because the verifier's output ended in a tool call and
   `unknown` fell through as a pass.
3. **Corrections can break the build.** On `014-T11` a senior correction step
   appended a duplicate style block to `App.svelte` (stray `air;`, orphan
   `</style>`) after the self-check had passed, and the run parked a broken tree.
4. **Quota walls spin.** 54 `429 free-models-per-day` errors, 471k tokens and
   20 minutes on `014-T10`, because free-only roles had no usable fallback and
   the harness retried the walled model.
5. **Caps that cannot fire.** A paid planner plus a paid coder made
   `estimate_run_cost` return `None`, which silently disabled
   `SWARM_MAX_COST_PER_TASK`; the aggregate estimate also over-reported 2.6×.
6. **Scope blindness.** `DEFAULT_SCOPE` had no `docs/`, so a documentation task
   could not write its own deliverable (fixed by `task_scope`).
7. **Claims without evidence.** `010-T4` was green having touched only
   `helpers.ts`; the Playwright suite had never run and contained four setup
   bugs plus NYC-only fixtures against Munich inputs.
8. **Silent config death.** A paid planner with `allow_paid=False` ended as a
   2-second `crew_error` with no message in `run.json`.
9. **Retry multiplication.** CrewAI's agent loop retried inside the harness's
   3 attempts: 20 LLM calls for one provider outage.
10. **Ledger fog.** A `spec.md` edit reopened `T2–T8` and a manual commit left
    `T1` without a trailer; nothing in the queue output said why.
11. **A spent wall budget disabled its own guard.** `007-T10` ran **2.7 h**
    against an 1800 s bound and ignored SIGTERM: the flow computes
    `remaining = budget - elapsed`, which goes negative once the budget is spent,
    and `run_bounded` read `timeout <= 0` as "no bound" — the watchdog switched
    itself off exactly when it was needed.

## Goal

Make every one of those shapes cheap, explicit and terminal **before** a model is
paid to discover it. The rule is: deterministic guards around model judgment,
fail-closed judges, and caps that cannot be silently disabled. Green stays
QA-owned; no gate, trailer or autonomy rule changes.

## Scope

- In scope:
  - A pre-verifier **delta guard**: empty delta, or a delta that misses the files
    the brief names, stops as `no_delta` / `delta_incomplete` with the missing
    paths in `run.json` and `human_log.txt`.
  - **Fail-closed judges**: no verdict, parse failure or empty output is red for
    the verifier, QA reviewer and senior paths; one bounded repair, then stop.
  - A **correction regression guard**: after each correction step run the cheap
    static checks; if a previously-green check is red, revert that correction
    (`correction_reverted`) and end the correction loop.
  - A **quota breaker**: N quota errors (default 3) on one provider end the run
    as `quota_exhausted`; fallbacks may only select models that can actually be
    called; preflight does a 1-token probe per configured role.
  - **Single retry authority**: agents run with `max_retry_limit=0`; the harness
    owns retries, backoff and typed errors.
  - **Cost fail-closed**: per-model pricing (already added) plus
    `cost_unknown: true` when any paid model is unpriceable, and a test with two
    paid models.
  - **E2E evidence**: a task whose brief names `frontend/e2e/*` is green only
    with an execution record; a `make e2e` target; preflight checks the
    Playwright config/browsers.
  - **Config errors carry text**, and preflight builds the same factories with
    the same flags as the run.
  - **Ledger diagnostics**: queue selection records *why* a task is open
    (`spec hash changed`, `missing trailer`); `make swarm-record SPEC TASK` for
    manual commits.
- Non-goals:
  - New model roles, a dispatcher, Postgres, or concurrent workers (ADR-012).
  - Changing QA-only gate evidence, commit trailers, scope secrets or the
    autonomy ladder.
  - Replacing the verifier: the delta guard checks *presence*, the verifier still
    checks *behaviour*.
  - Rewriting the e2e specs or app code; only their evidence and infrastructure.

## Acceptance criteria

- **AC-1 — Empty delta stops early.** If the coding phase leaves no in-scope
  delta, the run stops `needs_human` / `reason_code=no_delta` before the
  verifier and QA are called; `run.json` records the phase and the brief paths.
  `SWARM_DELTA_GUARD=0` restores the old behaviour.
- **AC-2 — Brief coverage.** If the brief names files and the delta touches none
  of them, the run stops `delta_incomplete` and lists the named-but-untouched
  paths. Files already present before the run do not count as touched.
- **AC-3 — Judges fail closed.** For the verifier, QA and senior paths, a
  missing/unparseable verdict is not green: one bounded repair call, then
  `needs_human` with the raw output tail recorded.
- **AC-4 — Corrections cannot regress the build.** After each correction step
  the cheap static checks run; if a check that was green before the correction
  is red after it, the correction's files are reverted, `correction_reverted`
  is recorded, and the correction loop ends.
- **AC-5 — Quota is terminal or usable.** Quota errors are counted per provider;
  at the limit the run ends `quota_exhausted` (not a retry loop). Fallback
  selection never returns a model the paid guard cannot call, and preflight's
  per-role probe fails fast on a wall.
- **AC-6 — One retry authority.** Agent objects are built with
  `max_retry_limit=0`; a single outage costs at most the harness's three typed
  attempts, and a test pins it.
- **AC-7 — Cost never silently unknown.** With two paid models `run.json.cost`
  is a number; when a paid model has no price row the run records
  `cost_unknown: true` and the budget note names it instead of pretending $0.
- **AC-8 — E2E evidence for e2e tasks.** A green run whose brief names
  `frontend/e2e/*` must contain a recorded e2e execution; otherwise
  `reason_code=e2e_missing`. `make e2e` boots the fixture backend and runs
  `playwright test` from `frontend/`.
- **AC-9 — Config errors are readable.** Every typed config failure writes the
  exception text to `run.json` (and `human_log.txt` names it); preflight builds
  each role with the same `allow_paid`/fallback flags the run uses.
- **AC-10 — The queue explains itself.** Queue selection records a reason per
  open task (`open`, `spec hash changed`, `task hash changed`, `missing
  trailer`), and `make swarm-record SPEC=… TASK=…` writes the standard trailers
  for a manually completed task.
- **AC-12 — The wall budget is terminal.** A zero or negative remaining budget
  refuses the call and stops as `wall_budget`; `run_bounded(None)` is the only
  unbounded mode; `run.json.wall_budget_note` names the phase; a test pins
  that a spent budget cannot start a call (007 ran 2.7 h because it could).
- **AC-11 — Tests and docs.** `make swarm-test` covers every guard with a
  passing and a failing case; `026-run-guards` is in `HARNESS_SPECS`;
  AGENTS/roadmap/changelog record the guards and their off switches.

## Evidence

Runs `20261114-183545` (T10 attempt 1), `20261114-184751` (T9), the three
`014-T10` attempts (`-183545`, `-2005xx`, `-2035xx`), `014-T11` (`-204x`),
`007-T10` (the 2.7 h wall-budget overrun), and the first `playwright test` run (5/10). Lessons recorded in
`AGENTS.md` ("A docs task could never write its deliverable", "green but never
mounted"), `changelog.md` 2026-11-14.

## Success definition

The six failure shapes cost one typed stop each, no verifier/QA spend after an
empty delta, no correction can leave a red build, a quota wall costs at most
three calls, a two-paid-model run reports a real cost, and an e2e task cannot be
green without an e2e execution record.
