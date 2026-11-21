# 041 Swarm Restructure Support — Spec

Harness spec (control plane; the queue never runs it).

## Problem

The swarm's coder cannot reliably do **restructure/refactor** tasks (the 040
UI restructure failed 6×). Two failure modes:

1. **Adds but doesn't remove.** The coder creates the new component but leaves
   the old form/sidebar in place, so the verifier blocks ("the form is
   duplicated") and a correction that fixes it breaks a static check
   (`correction_reverted`).
2. **No in-scope change.** The coder runs its steps (paid, ~95k tokens) but the
   delta guard reports `no_delta` — nothing landed in scope. The steps analyse
   instead of landing a file change.

The prompts don't tell the coder that a restructure must *replace* code (remove
what it supersedes) and that every step must *land* a change.

## Goal

The swarm handles restructure/refactor tasks: the coder removes the code it
replaces (no duplicates) and every step lands an in-scope file change.

## Scope (prompt rules in `swarm/prompts.py`)

- `STEP_RULES` — add two hard rules: (a) a step that replaces/restructures code
  must **remove the old code** it supersedes (never leave a duplicate); (b) every
  step must leave an **in-scope file change** (if it would leave none, write it).
- `PLAN_RULES` — for a restructure/refactor, split into **atomic steps** that each
  land a concrete file change (add/remove/modify) and name the exact file + action.

## Non-goals

- Changing the coder's tool set, the verifier, or the flow.
- New retry/fix-loop policy (this is prompt-side only).

## Acceptance criteria

- **AC-1 — Remove-old rule.** `STEP_RULES` contains an explicit "remove the old
  code you replace / no duplicates" instruction.
- **AC-2 — Land-a-change rule.** `STEP_RULES` contains an explicit "every step
  must leave an in-scope file change" instruction.
- **AC-3 — Atomic restructure planning.** `PLAN_RULES` contains an explicit
  "restructure/refactor → atomic steps that each land a file change, naming the
  exact file and action" instruction.
- **AC-4 — No regression.** `make swarm-test` stays green; the existing prompt
  tests still pass.

## Success definition

A restructure task (like 040-T1) runs to green: the coder removes the old
structure and the delta shows the in-scope change, instead of `no_delta` or
`correction_reverted`.
