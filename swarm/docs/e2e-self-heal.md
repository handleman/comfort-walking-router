# Self-healing e2e (027)

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

A task whose brief names `frontend/e2e/*` may only be green with a recorded
Playwright run (026). This page is what happens when that run is **red**: the
harness triages the failure, writes a small repair roster, runs it through the
pipeline, and refuses any repair that makes the suite pass by weakening it.

## Why a phase and not a fix round

A red e2e run is not one problem. One afternoon produced four different ones:
a stale test datum (arrival asserted at a point 1.9 km from the route's end), two
real product defects (a one-shot `locate`, a controls block that vanished on
arrival), and a harness argv that made every test fail for the wrong reason. Sent
to the normal coder loop, the first gets "fixed" by editing product code, the
second by editing the test, the third burns paid rounds. The phase separates
them first. `docs/research/self-healing-e2e-2026.md` is the market input: Donobu,
Playwright's healer, AutoCover, RoostGPT and Attractor all classify before they
touch anything, and all refuse to let the fixer grade its own work.

## What happens

```
QA records a red suite
        │
        ▼
TRIAGE (deterministic, no model)          swarm/e2e_triage.py
  env        → stop e2e_env               (no file edited)
  flaky      → stop e2e_flaky             (a retry passed)
  impl       → the code fix loop owns it  (spec edits refused)
  coverage   ┐ roster                     (the brief names a spec that is missing)
  drift      ┘                            (the element exists, the locator is stale)
        │
        ▼
ROSTER  <run>/inner/{spec,plan,tasks}.md  swarm/inner.py
  one `- [ ] T<n> (AC-…): brief` per failure, the queue's own format,
  scope = frontend/e2e/ only, ≤ SWARM_MAX_INNER_TASKS
        │
        ▼
REPAIR  fix crew works the roster → ANTI-WEAKENING GUARD → QA re-runs gates + suite
        │                                    → re-triage, ≤ SWARM_MAX_INNER_ROUNDS
        ▼
healed (recorded suite passes at the final delta) or a typed stop
```

Triaging and the roster are code, so a wrong verdict is a failing unit test
rather than a prompt to argue with. Only the repair itself needs a model.

## The guard is not phase-only

The first canary run (2026-11-15: one `button.walk-start` selector deliberately
broken) taught this the honest way. The suite came back green with
`e2e_self_heal: {}` — the **coder** had fixed the selector in the coding phase,
before QA ever ran, because the spec file is inside its scope. Two conclusions:

1. a `drift` canary in the same task is usually repaired before the phase can
   see it, so the phase's marginal value is the *triage* (a record of *why*) and
   the repairs that survive coding;
2. the anti-weakening guard was phase-only, which left the normal loop
   unguarded — the exact hole the guard exists to close.

So the check now runs on **any** run whose delta touches `frontend/e2e/`,
whether the editor was a coder, a fix round or the repair crew: the baseline
facts are captured with the run baseline, and `gate()` reverts and stops
`e2e_weakened` before a status is decided.

## The guard that makes it safe

`swarm/e2e_guard.py` compares the spec files before and after a repair:

- a test title that existed must still exist (no deletion, no rename-away);
- no `test.skip(`, `test.fixme(` or `.only(` may be added;
- the `expect(` count per file may not decrease.

A violation reverts exactly that repair's paths (archived in `<run>/reverted/`)
and stops the run as `e2e_weakened`. The final proof is separate and also
deterministic: the failing titles must appear **and pass** in a QA-recorded full
suite at the current delta hash, and the scenario verifier must still see the
brief implemented in the code.

That closing of the verification gap is the point: a repair that only satisfies
the rerun fails the title check or the verifier.

## Stops and knobs

| Stop | Meaning |
| --- | --- |
| `e2e_env` | the environment is broken (fixture backend, `DATABASE_URL`, browser); nothing is edited |
| `e2e_flaky` | a retry passed; a flake is never repaired |
| `e2e_weakened` | the repair deleted, skipped or weakened a check; it was reverted |
| `e2e_roster_overflow` | more failures than `SWARM_MAX_INNER_TASKS` — that is a broken suite |
| `e2e_unclassified` | the output could not be parsed; the phase never guesses |
| `e2e_rounds_exhausted` | the budget ran out with the suite still red |

| Knob | Default | Why |
| --- | --- | --- |
| `SWARM_E2E_SELF_HEAL` | `1` | `0` restores the 026 behaviour (red suite → normal fix loop) |
| `SWARM_MAX_INNER_TASKS` | `3` | more than three failures in one task is a broken suite, not a repair |
| `SWARM_MAX_INNER_ROUNDS` | `2` | repair → re-run twice; the second failure set is usually smaller |

Every run records `run.json.e2e_self_heal` (`class`, failing titles, roster,
rounds, reverted attempts, stop) and prints one line in `human_log.txt`:
`e2e self-heal: class drift (2 failing, 1 round(s)) — healed`.
`make swarm-report` counts the outcomes per stop.

## What is not done yet

- The phase's prompt cost is measured (`make swarm-bench`, 027 T8): for a
  synthetic red variant of each frozen case the triage digest is ~1.7k chars and
  the roster ~1.9k chars, both bounded — small enough that the phase never
  doubles a round's cost.
- No live drift repair has been observed yet: the canary was fixed earlier in the
  pipeline. The next experiment is a failure the coder cannot pre-empt — e.g. a
  spec that only fails after the fix round's own change — plus an `env` case with
  the fixture backend down.
- How often a repair is correct is still unmeasured. `e2e_self_heal` in every run
  and the escape rate are the inputs; the first real repair is the next test.
