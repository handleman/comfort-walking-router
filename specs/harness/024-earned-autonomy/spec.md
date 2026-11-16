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

Let a green run merge after the machine gates — the swarm is autonomous — and
record what kind of change it was (a risk label) so an escape-rate ratio per
class can be computed later.

**Decision 2026-11-15: autonomy is not a setting.** The first phase shipped a
ladder with three knobs (`SWARM_AUTONOMY`, `SWARM_AUTONOMY_MAX_CLASS`,
`SWARM_REQUIRE_APPROVAL`); the operator removed them because the point of the
project is the autonomous swarm. A green run whose gates are all `0`, whose
reviewer says `PASS` and whose verifier is not blocked merges in every class.
The label stayed (it is the escape-rate input); the ceiling and the on/off
switch went. The only hold is the per-run `--require-approval` flag.

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
- **AC-2 — The label is recorded, not consulted.** `risk.classify` labels the
  delta and `run.json.risk` carries `{class, label}` for every run; no gate and
  no merge decision reads it. (It read a ladder before the 2026-11-15 decision.)
- **AC-3 — Wiring.** On a green run, `save_run` records `payload["autonomy"]`
  and skips the `awaiting_approval` hold only when `auto_merge` is true; the
  commit still goes through `_commit_green` (branch, merge queue, trailers,
  push). An explicit `--require-approval` run without autonomy still holds.
- **AC-4 — Telemetry.** `run.json.autonomy` carries class, label,
  `gates_green`, `review_verdict`, `verifier_blocked`, `auto_merge` and
  `reason`; `human_log.txt` prints the class and the merge basis;
  `make swarm-report` counts runs per class and the auto-merged total.
- **AC-5 — No autonomy setting.** There is no on/off switch and no class
  ceiling: `SWARM_AUTONOMY*` and `SWARM_REQUIRE_APPROVAL` are removed from the
  code, `.env.example` and the docs, and a test pins their absence. The only
  hold is the explicit `--require-approval` flag (`make swarm-approve`).
- **AC-6 — Tests and docs.** `make swarm-test` covers the ladder, sensitive
  briefs, every decision branch, the wiring and the telemetry without an LLM;
  `024-earned-autonomy` is in `HARNESS_SPECS`; `AGENTS.md`, `docs/roadmap.md`
  and `changelog.md` record the result.
- **AC-7 — Honest measurement.** Autonomy is the default and the escape rate
  (`swarm/escape.py`, every green run counts as merged) is a floor: a hand-fixed
  regression is not a detected escape. That ratio, per class, is the only signal
  that would justify reintroducing a ceiling.

## Evidence

`docs/research/dark-factory-market-2026.md` (risk classes 0–3, earned autonomy,
escape-rate telemetry), `specs/012` (approval hold), `specs/013` (commit
trailers, approval-resume), the 020–023 measurements (no green live baseline
yet).

## Success definition

A docs/test-only green task can merge without a human when autonomy is enabled,
a logic/control change cannot, and every run says exactly why.
