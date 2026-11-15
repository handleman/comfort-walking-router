# 027 E2E Self-Heal — Spec

Control-plane spec (add `027-e2e-self-heal` to `HARNESS_SPECS`): the queue never
implements it.

## Problem

026 taught the harness to *require* a recorded Playwright run for a task whose
brief names `frontend/e2e/*` (AC-8). The obvious next step is missing: when that
run is **red**, the harness has no way to act on it. It hands the failure to the
same coder fix loop as any other red gate, so three things happen instead of a
repair:

1. a **test-side** breakage (a renamed selector, a fixture that drifted from the
   API) is fixed by editing implementation code until the test passes — the tail
   wags the dog;
2. a **missing scenario** (the brief names an e2e file that does not exist yet)
   has no owner: the coder's scope excludes `frontend/e2e/`, so the run stops;
3. an **environment** failure (`DATABASE_URL` unset, no browser, fixture backend
   down) is treated as a code defect and burns paid rounds before a human sees
   the real cause. The 2026-11-15 e2e runs lost time to exactly this.

The 2026-11-14/15 lesson is blunt: the run can be green while the suite was never
run, and it can be red for a reason no code change can fix. A dark factory that
stops on every red e2e test is not dark; one that lets the model rewrite the
oracle to make it green is not a factory. `docs/research/self-healing-e2e-2026.md`
surveys the market: every serious system separates *test-side repair* from
*product defects* and *environment failures*, bounds the rounds, and refuses to
let the fixer grade its own work.

## Goal

When the recorded e2e run is red, the harness **triages** the failure, writes a
small **inner roster** (spec → plan → tasks for the repair, inside the run dir),
runs that roster through the existing pipeline (planner → coder/test-author →
self-check → verifier → QA gates), and re-runs the whole suite. Bounded, typed,
and impossible to satisfy by weakening the test.

## Scope

- `swarm/e2e_triage.py`: parse a failed Playwright run into failing tests with
  titles, files and an error class; `classify()` → `env` / `impl` / `drift` /
  `coverage` / `flaky` with a deterministic decision table (reporter fields, error
  text, fixture health, whether the named spec exists).
- `swarm/inner.py`: write `<run>/inner/spec.md`, `inner/plan.md` and
  `inner/tasks.md` in the same `- [ ] T<n> (AC-…): brief` format the queue reads,
  one task per failure, each naming its AC, the failing title, the allowed files
  and the acceptance. Bounded by `SWARM_MAX_INNER_TASKS` (3).
- A triage role (read + the roster file only) that turns the failure digest into
  roster entries; `SWARM_TRIAGE_MODEL` (default: the senior model).
- Flow wiring: after a red recorded e2e run and before the normal fix loop; the
  inner tasks run with `task_scope` restricted to `frontend/e2e/**` for
  `drift`/`coverage`, and to the implementation paths for `impl`; `env` stops
  immediately; `flaky` changes nothing.
- `swarm/e2e_guard.py`: the anti-weakening guard — no removed test titles, no
  `skip`/`fixme`/`only`, assertion count non-decreasing, and the originally
  failing titles present *and passing* in the final recorded run.
- `run.json.e2e_self_heal` (`class`, failing titles, roster, rounds, weakened,
  stop reason) and a `human_log.txt` line; `make swarm-report` counts them.
- `SWARM_E2E_SELF_HEAL=0` off switch, `SWARM_MAX_INNER_TASKS=3`,
  `SWARM_MAX_INNER_ROUNDS=2`.

## Non-goals

- Generating a whole e2e suite from scratch, or replacing the reviewed specs.
- Healing class `env` or `impl` failures by editing tests (refused by scope).
- A second gate runner: QA stays the only agent that runs the suite for evidence.
- Auto-committing inner tasks separately: they fold into the outer run's delta and
  trailers (one task, one commit, one done-ledger entry).
- Changing 026 AC-8: the final recorded run is still mandatory for green.

## Acceptance criteria

- **AC-1 — Deterministic triage.** `e2e_triage.classify()` maps a recorded failure
  to `env` (fixture backend down, missing `DATABASE_URL`/browser/port, DNS), `flaky`
  (passed on retry), `coverage` (the brief names a spec file that does not exist),
  `impl` (the app is missing the behaviour the spec asserts), or `drift` (the
  element/route exists but the spec's locator or fixture is stale). Every branch is
  tested from recorded reporter output; no model call is needed for either the
  parse or the table.
- **AC-2 — The inner roster is a real SDD artifact.** For `drift`/`coverage`,
  `<run>/inner/{spec,plan,tasks}.md` exist, parse with
  `spec_loader.parse_tasks_md`, and each task names one failing title, its AC, the
  allowed paths and its acceptance. More than `SWARM_MAX_INNER_TASKS` failures stop
  the phase as `e2e_roster_overflow` instead of producing an unbounded queue.
- **AC-3 — The phase never replaces the judges.** It runs after a red recorded
  suite and before the fix loop; it writes no gate evidence, cannot change `gates`
  or `review_verdict`, and green still needs a QA-recorded full suite at the final
  delta hash (026 AC-8).
- **AC-4 — The repair is scoped by class.** `env` stops as `e2e_env` with no file
  edited. `impl` lets the coder touch implementation paths only (`frontend/src/`,
  `app/`, …) and no test. `drift`/`coverage` let the writer touch `frontend/e2e/**`
  (and its fixtures) only. A write outside the class's scope is refused by the
  tools and recorded.
- **AC-5 — Weakening is refused deterministically.** After any roster task:
  removing a test title, adding `skip`/`fixme`/`only`, or lowering the assertion
  count reverts that task's paths (archived in `<run>/reverted/`) and stops as
  `e2e_weakened`; the originally failing titles must exist in the final run.
  `SWARM_E2E_SELF_HEAL=0` disables the phase and restores today's behaviour.
- **AC-6 — Green after a repair is evidence, not a claim.** The final recorded run
  passes at the current delta hash, contains the originally failing titles, and
  the diff still satisfies AC-5; `run.json.e2e_self_heal` records the class, the
  failing titles, the roster, the rounds, any reverted attempt and why it stopped.
- **AC-7 — Bounded and typed.** `SWARM_MAX_INNER_ROUNDS` (2) bounds the
  repair→re-run loop; every stop is a typed reason (`e2e_env`, `e2e_weakened`,
  `e2e_roster_overflow`, `e2e_unclassified`) and appears in `human_log.txt`.
- **AC-8 — Tests and docs.** `make swarm-test` covers the decision table, the
  roster format, the scope split, the weakening guard and the stop paths without an
  LLM; a frozen failing-run fixture renders the triage prompt with no model call
  (`make swarm-bench`); docs get one page ("Self-healing e2e"), and
  `docs/research/self-healing-e2e-2026.md` is the market input.

## Evidence

`docs/research/self-healing-e2e-2026.md` (Donobu, Playwright healer, AutoCover,
RoostGPT/Rainforest, Attractor/DTU, BrainGu verification gap). Our own runs:
`20261114-*` (010-T4 green without a suite), `20261115-1259*` (007-T10: a red
walk-mode suite and 30 minutes of fix rounds), the `preferences.spec.ts` skip
without `DATABASE_URL` (an environment failure that looked like code).

## Success definition

A red e2e suite either gets a **planned, scoped, bounded repair** that survives the
full suite and the verifier, or the run stops with one typed reason a human can act
on in a minute — and no path exists by which a model makes the suite green by
deleting, skipping or weakening what it asserts.
