# 049 Senior Escalation on Verifier Block — Spec

Harness spec (control plane; the queue never runs it).

## Problem

A task that ends `verifier_blocked` never reaches the senior agent. The
senior-escalation loop is gated on `not verifier.blocked`
(`swarm/flow.py:3712`):

```python
if not _gates_green(gates) and not self.state.verifier.get("blocked"):
    # senior escalation loop …
```

When the verifier blocks, the flow stops straight to `needs_human`; the senior
(`build_senior_crew`, the escalation brain) is never called. The verifier's own
correction passes run the *coder* (`build_step_crew`, `coder:verify<n>`), not the
senior, so a scenario defect that the coder can't resolve is never escalated.

Observed 2026-11-23 on the Go profile: three tasks parked as `retry_later` after
three `needs_human`/`verifier_blocked` attempts each — `039 T1`,
`040 T16`, `040 T18` — with **zero senior rounds** (`run.json.senior_used` false
on each). The operator's request is exactly that gap: give the senior one real
attempt before a task is parked as human-required.

## Goal

When the verifier blocks, the flow makes **one** bounded senior fix attempt fed
with the verifier's findings, then re-verifies. If the senior unblocks it, the
task continues to QA/gates and can go green; if it is still blocked, the run
ends `verifier_blocked` as today (no loop). This is in-flow, so *every*
supervisor attempt already carries the senior pass — a task that still parks
after three attempts has genuinely had three senior looks.

## Design

- **Trigger.** After the dev loop, when `self.state.verifier.get("blocked")` is
  true and no senior verify-round has run yet (`senior_rounds` on the blocked
  path < 1), escalate once.
- **Crew.** The existing `build_senior_crew(self._spec_dir, task, report, note)`
  (045 `_senior_agent`, deep-fix prompt). Its `report` is the verifier's stored
  report (`state.verifier["report"]`, already `verify.render_report` at
  `flow.py:2479`); fall back to the `findings` list. `note` is the verifier's
  `note`.
- **Re-verify.** After the senior round, call `_verify_phase(task, kick)` again
  (it re-reads the tree from a clean `state.verifier={}`). If it returns `True`
  and the verifier is no longer blocked, fall through to the normal QA/gates
  green determination. If still blocked, stop — bounded, no extra rounds.
- **Bounded.** Exactly one senior round on this path (not `SENIOR_ATTEMPTS=2`),
  so a verifier that can never be satisfied spends one senior call, not a loop.

## Non-goals

- Not changing the normal (gates-red) senior loop, `SENIOR_ATTEMPTS`, or the
  verifier's own coder-correction rounds.
- Not a supervisor-level "force senior" flag — the flow already escalates; the
  only change is it now also escalates on a block.
- Not touching the parked `retry_later` bookkeeping (re-parking still happens
  after `max_attempts`, unchanged).

## Acceptance criteria

- **AC-1 — Escalate on block.** When `_verify_phase` ends with `blocked` true,
  the flow runs exactly one `build_senior_crew` round before returning
  `verifier_blocked`.
- **AC-2 — Fed the findings.** The senior round's report carries the verifier's
  findings/report (not an empty QA report).
- **AC-3 — Re-verify, can go green.** If the senior fix changes the tree and the
  re-run verifier passes, the task proceeds to QA/gates and may be committed
  green; if the re-run verifier still blocks, the run ends `verifier_blocked`.
- **AC-4 — Bounded.** A verifier that blocks every time costs at most one senior
  round per flow attempt (`senior_rounds` on this path never exceeds 1 per run).
- **AC-5 — Recorded.** `run.json` shows `senior_used`, `senior_rounds`, and a
  `verifier` note (e.g. `senior_escalation_on_block`) so the dashboard/report can
  see the senior was tried.
- **AC-6 — No regression.** `make swarm-test` stays green; new fixture tests
  cover (a) block → senior round → re-verify → green, and (b) block → senior
  round → still blocked → `needs_human`.

## Files

- `swarm/flow.py` — insert the bounded senior round + re-verify on the blocked
  path (around `run_crew`'s end-of-dev-loop, before the final status mapping).
- `swarm/tests/test_verify.py` / `test_autoloop.py` — fixture tests (AC-6).
- `specs/harness/049-senior-on-verifier-block/` — spec, plan, tasks.

## Success definition

For a task that today parks as `verifier_blocked` (e.g. `040 T16`), the flow
shows `senior_used: true`, one senior round, a re-verify, and either a green
commit or a genuinely human-required stop — never a silent skip of the senior.
