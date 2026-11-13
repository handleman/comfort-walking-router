# 022 Lean Loop — Spec

Control-plane spec (added to `HARNESS_SPECS`): the queue never implements it.

## Problem

021 made the loop *correct*: the verifier no longer re-litigates, a step must
land its file, key lines survive, and repair routing reaches the senior model.
It also measured the next wall: **latency**.

The paid-coder bake-off on `007-live-position-T2` (two files):

| Run | Configuration | Result |
| --- | --- | --- |
| 1 | paid coder / local QA | 2 steps, **all six gates green in ~5 min**, then a fix call hung |
| 2 | paid coder / local QA, 60 s timeout | gates ran, local 9.7 B QA **hung ~9 min** on the verdict |
| 3 | paid coder / fast cloud QA, 900 s | no hang; gates + verdict + fix loop, **cap hit while working** |
| 4 | same, 1500 s | QA + fallback + fix + retry, **cap hit again** |

The loop has roughly **ten sequential model phases** — planner, N steps,
self-check, verifier, QA, fix rounds, retries. At 30–90 s per call that is
10–25 minutes before the outcome is decided, and the 021 suite could not finish
a case inside 2400 s. More tokens are not the problem anymore (020), and more
correctness is not the problem (021). **Serial wall clock is.**

## Goal

Make one task finish predictably: every phase has a time budget, independent
phases run concurrently where it is safe, a slow model call cannot silently eat
the whole task, and the outcome suite completes with a row per case instead of a
timeout.

## Scope

- Per-phase timing in `run.json`, aggregated by `make swarm-report`.
- A per-task wall-clock budget enforced **between phases**, with a copyable stop
  reason (`wall_budget`), so a stuck run ends at a known point.
- Concurrent verification: the 019 verifier and QA run against the same delta at
  the same time when enabled and safe, with both still required for green.
- A lean path that skips the scenario verifier for low-risk diffs, opt-in and
  measured (the minimal risk classifier 023 will build on).
- Retry economics: separate timeouts for fix/verifier calls, retries recorded,
  and no retry that cannot fit the remaining budget.
- A completed outcome-suite baseline and a before/after wall-clock table.

## Non-goals

- Parallel **tasks** / workers (that is 023; single-task latency comes first).
- Earned auto-merge and risk-class policy (023).
- Changing the green definition, QA-only gate evidence, or the verifier's
  read-only contract.
- More token/char compaction (020 covered it).

## Acceptance criteria

- **AC-1 — Phase timing.** Every phase (plan, each step, self-check, verifier,
  QA, each fix round, each retry) records `started_at`, `ended_at`,
  `duration_seconds` and its role/model in `run.json.phases`; durations are
  derived from `events.jsonl`, not from a second clock. `make swarm-report`
  prints p50/p90 per phase and the share of the task wall clock.

- **AC-2 — Wall budget.** `SWARM_TASK_WALL_BUDGET` (default 900 s; `0` disables)
  is checked between phases and before a retry. On breach the run stops as
  `needs_human` with `reason_code=wall_budget`, `human_log.txt` naming the phase
  that consumed the budget, and the run record intact. The replay runner sees a
  completed row, not a timeout.

- **AC-3 — Concurrent verification.** `SWARM_VERIFY_CONCURRENT=1` (default `0`
  until measured) runs the 019 verifier and the first QA round concurrently on
  the same delta. Both must pass for green; a verifier block after QA green
  still blocks. Event writes stay append-only and are serialised through the
  existing listener; the two crews never write the same file (the verifier is
  read-only and runs no gate). `=0` restores the sequential order.

- **AC-4 — Lean path for low-risk diffs.** `SWARM_VERIFY_LEAN=1` (default `0`)
  skips the scenario verifier when the run delta is low-risk: only docs/tests/
  config paths, or a small mechanical change (bounded lines/paths), and all
  gates are green. Any path outside the low-risk set, or a change above the
  bound, verifies as today. The classifier and its decision are recorded in
  `run.json.verifier` (`skipped_reason`), so a skipped verification is visible.
  This is the minimal risk classifier 023 expands into class 0–3.

- **AC-5 — Retry economics.** Fix and verifier calls get their own timeout
  (`SWARM_LLM_FIX_TIMEOUT_SECONDS`, default 180 s) instead of the 90 s used for
  chat-like calls; a timed-out call records `llm_timeout` (role, phase, elapsed)
  and does **not** trigger a retry whose worst case cannot fit the remaining
  wall budget. Retries are counted in `run.json.retries` and reported.

- **AC-6 — Measured wall clock.** The outcome suite runs with the budget:
  every selected case produces a row (green or an explicit stop), and the
  before/after table lands in `docs/research/fix-loop-2026.md` and
  `changelog.md`. Targets: a two-file case completes in **p50 ≤ 10 min**,
  the five-case suite completes in **≤ 45 min**, and the green rate is **not
  lower** than the 021 baseline. A variant that lowers green is reverted.

- **AC-7 — Knobs, defaults and docs.** `SWARM_TASK_WALL_BUDGET`,
  `SWARM_VERIFY_CONCURRENT`, `SWARM_VERIFY_LEAN`, `SWARM_LLM_FIX_TIMEOUT_SECONDS`
  are documented in `.env.example` and `swarm/README.md`. Disabling every knob
  restores the 021 order and budgets. `make swarm-test` covers both paths;
  concurrency has a test with a fake verifier/QA pair.

- **AC-8 — Close-out.** `HARNESS_SPECS` contains `022-lean-loop`; `AGENTS.md`,
  `docs/roadmap.md` and `changelog.md` record the measured result and the
  keep/revert decision for concurrency and the lean path. 023 (parallel tasks
  and earned autonomy) follows only after this phase's numbers.

## Evidence

- `docs/research/fix-loop-2026.md` (paid bake-off, four capped runs, sequential
  phases), `specs/021-fix-loop/`, `swarm/bench/replay.py`, `swarm/flow.py`.
- Market: repair gains flatten after 3–4 rounds and orchestration/feedback
  design dominates ([Is Three the Magic Number?](https://doi.org/10.1145/3832783.3834547));
  Google's AutoRepair bounds the loop with a hard runtime cap
  ([AutoRepair](https://arxiv.org/html/2610.07289v1)).

## Success definition

A task's wall clock is predictable and bounded, and the outcome suite completes
with a per-case table. The phase does not claim speed from more parallelism; it
removes serial waiting first.
