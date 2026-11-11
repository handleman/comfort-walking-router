# 017 Coder Self-Check — Spec

Control-plane spec (added to `HARNESS_SPECS`): the queue never implements it.

## Problem

On 2026-11-11 the 007-T9 run spent **three QA rounds and two coder rounds** on a
single type error:

```
frontend/src/lib/navigation/walk.integration.test.ts:156:21
Error: Property 'tick' does not exist on type 'PositionProvider'.
```

The check had named the file, the line and the cause. The QA gatekeeper reported
it four times, the coder round read the file, and the work still was not fixed —
the defect was a one-line mismatch between a test and the interface it used.

The harness had no phase between "the coder wrote the code" and "QA reviews it":
the first type error was found by QA, and the only feedback loop was the
QA→coder→QA round-trip, which costs a reviewer call plus a full gate run per
attempt.

## Goal

The coder must not hand work on with a red type check or a red linter. The
harness runs the project's *static* checks right after the micro-steps and gives
the coder the evidence while the work is still his — before QA spends a review.

## Acceptance criteria

- **AC-1** — Before QA is asked to review, the harness runs the project's static
  checks (type checker + linter; never the test suites) and records the exit
  code of each.
- **AC-2** — A red static check produces a bounded, actionable report for the
  coder: the failing command, its exit code, `file:line: message` key lines and
  the raw output.
- **AC-3** — The coder gets a fix round with that report (no gates: QA stays
  the only gate executor), and the static checks are re-run. The number of fix
  rounds is bounded.
- **AC-4** — The self-check never makes a run green: its executions are recorded
  under their own agent role and are never counted as QA evidence.
- **AC-5** — The commands are configuration, not a harness assumption:
  `SWARM_SELF_CHECK_COMMANDS` (explicit) or the static subset of
  `SWARM_GATE_COMMANDS` (derived); `SWARM_SELF_CHECK=0` disables the phase.
- **AC-6** — A formatting-only failure is still repaired by the harness
  (the formatter), never by a coder round; the coder only sees real code
  problems.
- **AC-7** — The phase is visible: `run.json.self_check` records the commands,
  their exit codes, the red ones and the number of fix rounds.

## Non-goals

- The self-check is not a gate and does not replace QA's evidence.
- It does not run the test suites (they stay QA's).
- It does not change who may run gates: coders still cannot.
