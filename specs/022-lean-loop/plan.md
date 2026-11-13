# 022 Lean Loop — Plan

Status: in progress (T1 phase timing, T2 wall budget, T3 timeouts done). References `specs/022-lean-loop/spec.md` AC-1–AC-8 and
`docs/research/fix-loop-2026.md` (the paid bake-off that measured ~10 sequential
phases and four capped runs).

## Approach

The loop is correct enough; it is too **serial**. Measure every phase, bound the
task, run the two independent verifications together, and remove the verifier
from diffs that cannot hide the 014 class. Every risky change is opt-in and
decided by the outcome suite.

```
T1  phase timing from events + report
      │
      ├─ T2  wall budget + reason_code=wall_budget
      │
      ├─ T3  fix/verifier timeouts, retry counting, budget-aware retries
      │
      ├─ T4  verifier ∥ QA (opt-in, both must pass)
      │
      ├─ T5  lean path: skip the verifier for low-risk diffs (opt-in)
      │        │
      │        └─ T6  outcome suite with the budget; before/after table
      │                 │
      │                 └─ T7  keep/revert each variant
      │                          │
      └──────────────────────────┴─ T8  close-out: HARNESS_SPECS, docs, gates
```

T1–T3 are deterministic and low risk: they cannot make a run green, they only
make its time visible and bounded. T4/T5 change what runs, so both are flag-off
until T6 measures them. T6 must produce a complete table; a case that hits the
budget is a row with `wall_budget`, not a missing case.

## T1 — phase timing

- Derive `run.json.phases` from `events.jsonl`: each `crew_started`/`crew_done`
  pair (and harness shell phase) becomes `{phase, role, started_at, ended_at,
  duration_seconds, model}`. No second clock.
- `make swarm-report`: p50/p90 per phase, total task wall clock, and the share
  of the slowest phase. A fixture with synthetic events tests the derivation.

## T2 — wall budget

- `SWARM_TASK_WALL_BUDGET` (default 900 s, `0` off), checked by the flow
  **between phases** and before a retry (`_check_task_budget` already exists for
  seconds; extend it with the wall clock and a per-phase message).
- On breach: `status=needs_human`, `reason_code=wall_budget`, `human_log.txt`
  names the phase and elapsed/total. Never mid-crew kill: the current call
  finishes, then the budget decides.
- The replay runner already kills at its own cap; with this, the flow stops
  first and writes `run.json`, so the suite gets a row.

## T3 — retry economics

- `SWARM_LLM_FIX_TIMEOUT_SECONDS` (default 180) applies to fix/senior/verifier/
  correction crews; chat-like planner/QA keep `SWARM_LLM_TIMEOUT_SECONDS` (90).
- Record `llm_timeout` events (`role`, `phase`, `elapsed`) and `run.json.retries`.
- Before a retry, check the remaining wall budget; if the worst case cannot fit,
  stop with `wall_budget` instead of starting another call.
- This is the run-4 lesson: a 90 s Zen timeout caused a `task_failed` and a retry
  that doubled the wall clock.

## T4 — verifier ∥ QA

- When `SWARM_VERIFY_CONCURRENT=1` and the verifier is enabled, run the 019
  verifier and the first QA round in two threads against the same delta.
  - The verifier is read-only and runs no gate; QA runs gates and appends to
    `shell_log.jsonl`. The event listener is the only shared writer: guard it
    with a lock (`SwarmListener`) so events cannot interleave mid-line.
- Both must pass. If QA green and the verifier blocks, the run is not green;
  the verifier's corrections run afterwards as today.
- If the verifier is disabled or `=0`, keep the sequential order.
- Tests: a fake verifier/QA pair with sleeps asserts both results are combined
  and the wall clock is `max`, not `sum`.

## T5 — lean verifier path

- `SWARM_VERIFY_LEAN=1` (default `0`): skip the scenario verifier when the run
  delta is low-risk — every changed path under `docs/`, `tests/` (test-only
  changes), `contracts/` docs, or a mechanical change within
  `SWARM_LEAN_MAX_LINES`/`SWARM_LEAN_MAX_PATHS` — and all gates are green.
- Any implementation path (`app/`, `frontend/src/`) or a larger diff verifies as
  today. The decision and reason land in `run.json.verifier.skipped_reason`.
- Tests: a docs-only delta skips; an `app/main.py` delta never does; an
  oversized test delta never does; the flag off restores verification.

## T6 — measured wall clock

Run the five-case suite with the paid/fast pin from the bake-off, the budget,
and each variant:

| Arm | Configuration |
| --- | --- |
| baseline | 021 order, budget on (T1–T3) |
| concurrent | + `SWARM_VERIFY_CONCURRENT=1` |
| lean | + `SWARM_VERIFY_LEAN=1` |

Record green, wall clock, per-phase p50, retries and cost in
`docs/research/fix-loop-2026.md`. Targets: two-file case p50 ≤ 10 min, suite
≤ 45 min, green not lower than the 021 baseline.

## T7 — keep/revert

Keep concurrency and the lean path only on a measured wall-clock win with no
green loss; otherwise revert to the flag-off default and record the negative
result. The wall budget and timing stay regardless (they are observability).

## T8 — close-out

- `HARNESS_SPECS += ("022-lean-loop",)`.
- `swarm/README.md`: phase timing, the budget, the two A/Bs, the retry knobs.
- `AGENTS.md`, `docs/roadmap.md`, `changelog.md`: the measured numbers and the
  keep/revert decision; 023 (parallel tasks + earned autonomy) next.
- `make swarm-test`, `ruff check .`, `mypy app tests`.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Concurrent event writes interleave/corrupt | One lock in the listener; append-only JSONL; a test hammers it from two threads |
| Concurrency changes a verdict | Both must pass; sequential fallback; A/B on the suite |
| Lean path skips the 014 class | Only docs/tests/mechanical paths and a small bound; implementation paths always verify; the skip is recorded |
| Wall budget cuts a legitimate local run | Default 900 s is above the observed p50 for a small task; `0` disables; a local run can raise it |
| Phase timing adds a second source of truth | Derived from `events.jsonl`; no new write path |
| A retry cannot fit and is skipped | That is the intent: `wall_budget` with the reason, instead of a half-finished call |
