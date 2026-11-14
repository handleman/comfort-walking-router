# 024 Earned Autonomy — Spec

Control-plane spec (added to `HARNESS_SPECS`): the queue never implements it.

## Problem

The harness can now reach a **green** run whose gates and verifier passed, and
still stop at `awaiting_approval` for a human merge. Every green costs a human
interrupt, including documentation and test-only changes that the machine
already proved. The market settled on a ladder rather than a switch: low-risk
classes merge after the machine gates, high-risk classes wait, and expansion is
earned from measured agreement and escape rates.

There is no risk class and no auto-merge decision in `run.json` today, so an
autonomy policy cannot be evaluated or withdrawn on evidence.

## Goal

Let **class 0 (docs) and class 1 (tests)** merge after gates + the scenario
verifier when autonomy is explicitly enabled, keep class 2 (logic) and class 3
(control-plane/auth/migrations/unknown) human, and record every decision so an
escape-rate ratio can be computed later.

## Scope

- A path/brief risk classifier (0 docs, 1 tests, 2 logic, 3 control/unknown).
- `SWARM_AUTONOMY=1` (default 0) + `SWARM_AUTONOMY_MAX_CLASS=1`.
- The approval hold consults the decision; an earned auto-merge commits through
  the existing green path.
- `run.json.autonomy` with class, label, gates/verdict/verifier inputs, the
  decision and its reason.
- `human_log.txt` and `make swarm-report` show the class and the auto-merged
  count.

## Non-goals

- Auto-merging class 2/3, deploying to production, or weakening QA-only evidence.
- Diff-content risk scoring (semantic change size) beyond paths and brief
  keywords.
- Automatic escape-rate measurement (post-merge revert detection); the decision
  record is the input for it.
- Changing the approval path for explicit `--require-approval` runs.

## Acceptance criteria

- **AC-1 — Risk ladder.** `risk.classify(changed, brief)` returns 0 for
  docs/`*.md`, 1 for tests/e2e, 2 for `app/`, `frontend/src/`, `contracts/`,
  and 3 for `swarm/`, `specs/`, migrations, auth/payments/infra, configuration
  and any unknown path. An empty delta is 3. A sensitive brief (auth, payment,
  migration, infra, secret) is 3 regardless of paths.
- **AC-2 — Earned decision.** `risk.decision` allows auto-merge only when
  autonomy is on, class ≤ `SWARM_AUTONOMY_MAX_CLASS`, every gate is green, the
  reviewer verdict is `pass`, and the verifier is not blocked. It records a
  reason for both outcomes (off, class too high, gates red, reviewer, verifier).
- **AC-3 — Wiring.** On a green run, `save_run` records `payload["autonomy"]`
  and skips the `awaiting_approval` hold only when `auto_merge` is true; the
  commit still goes through `_commit_green` (branch, merge queue, trailers,
  push). An explicit `--require-approval` run without autonomy still holds.
- **AC-4 — Telemetry.** `run.json.autonomy` carries class, label,
  `gates_green`, `review_verdict`, `verifier_blocked`, `auto_merge` and
  `reason`; `human_log.txt` prints the class and the merge basis;
  `make swarm-report` counts runs per class and the auto-merged total.
- **AC-5 — Knobs and off switch.** `SWARM_AUTONOMY` (default `0`) and
  `SWARM_AUTONOMY_MAX_CLASS` (default `1`) are documented in `.env.example` and
  `swarm/README.md`; `SWARM_AUTONOMY=0` restores the human hold exactly.
- **AC-6 — Tests and docs.** `make swarm-test` covers the ladder, sensitive
  briefs, every decision branch, the wiring and the telemetry without an LLM;
  `024-earned-autonomy` is in `HARNESS_SPECS`; `AGENTS.md`, `docs/roadmap.md`
  and `changelog.md` record the result.
- **AC-7 — Honest measurement.** No live auto-merge is claimed until a green
  baseline exists. Expansion to class 2 and withdrawal are driven by measured
  agreement and escape rates (recorded as the next decision, not this phase).

## Evidence

`docs/research/dark-factory-market-2026.md` (risk classes 0–3, earned autonomy,
escape-rate telemetry), `specs/012` (approval hold), `specs/013` (commit
trailers, approval-resume), the 020–023 measurements (no green live baseline
yet).

## Success definition

A docs/test-only green task can merge without a human when autonomy is enabled,
a logic/control change cannot, and every run says exactly why.
