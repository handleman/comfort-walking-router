# 027 E2E Self-Heal — Plan

## Shape

One extra phase, placed where the harness already knows the suite is red:

```
QA runs the gates + the suite ──green──► 026 evidence check → green
        │red (recorded playwright run)
        ▼
E2E TRIAGE (deterministic parse + table, one cheap model call only to describe)
   ├─ env       → stop  e2e_env         (no file edited)
   ├─ flaky     → stop  e2e_flaky       (a retry passed; never edit for flake)
   ├─ impl      → normal fix loop, scope = implementation, tests refused
   ├─ drift     ┐ inner roster (spec/plan/tasks under <run>/inner/)
   └─ coverage  ┘ → plan → coder/test-author → self-check → verifier
                     ↓ per task: ANTI-WEAKENING GUARD (deterministic)
                     └ re-run the whole suite (QA) → triage again, ≤2 rounds
```

## Modules

- `swarm/e2e_triage.py`
  - `failing_tests(executions, current_hash) -> list[FailedTest]` — reads
    `shell_log.jsonl`; the last Playwright record wins; parses the JSON reporter
    when present, else the line reporter's `✘ [chromium] › file:line › title`.
  - `classify(failed, *, spec_exists, fixture_ok, retried_pass) -> str` — the
    decision table; pure, no model.
  - `digest(failed) -> str` — the bounded prompt block (title, file, error class,
    first error line, and the spec's own source excerpt for `drift`).
- `swarm/inner.py`
  - `write_roster(run_dir, spec_id, task_id, failures, classes) -> Roster` — writes
    `inner/spec.md` (problem, per-failure AC and acceptance), `inner/plan.md`
    (approach per class), `inner/tasks.md` (`- [ ] T1 (AC-…): brief` lines).
  - `load_roster(run_dir) -> list[SpecTask]` — reuses
    `spec_loader.parse_tasks_md`, so the roster is the same format as `specs/`.
  - `scope_for(cls, task) -> tuple[str, ...]` — `drift`/`coverage`:
    `frontend/e2e/`; `impl`: the product paths of the outer task, never a test.
- `swarm/e2e_guard.py`
  - `titles(run_dir) -> set[str]` from `playwright test --list` records, and
    `title_passed(run_dir) -> set[str]`.
  - `weakened(before_titles, after_titles, before_asserts, after_asserts, text)` —
    returns the reasons: removed titles, `skip`/`fixme`/`only`, fewer `expect(`.
- `swarm/flow.py`
  - `_e2e_self_heal_phase(task, changed)` called from `_gates_or_evidence` when a
    recorded suite is red and `evidence.e2e_required(...)`.
  - Uses the existing `_kickoff`/`_review`/`_verify_phase`/`_static_codes` path with
    `gate_scope()`/`task_scope()` set from `scope_for`, and `run_delta` bounded to
    the inner task's paths.
  - `_run_roster_task(...)` invokes `build_test_author_crew` for `coverage` and the
    normal step/fix crews for `drift`.
  - State: `e2e_self_heal: dict` (`class`, `failed`, `roster`, `rounds`,
    `weakened`, `reverted`, `stop`), `reason_code` additions
    (`e2e_env`, `e2e_flaky`, `e2e_weakened`, `e2e_roster_overflow`,
    `e2e_unclassified`).

## The decision table (deterministic)

| Signal | Class |
| --- | --- |
| recorded run has `retry`/`flaky` pass for the title | `flaky` |
| `400 response`/`5xx` from a URL that is the fixture backend, or a fixture app log line `connect ECONNREFUSED` | `env` |
| the brief names `frontend/e2e/x.spec.ts` and the file does not exist | `coverage` |
| `getByRole/getByLabel`/`locator` not found **and** the same element exists under a different accessible name in the page snapshot the healer takes | `drift` |
| assertion mismatch on a visible element, or route 404 from the app itself | `impl` |
| anything else | `unclassified` (stop, never guess) |

Only `drift` needs a look at the running page, and that look is the triage role's
read-only browser/HTML dump — no writes. The table itself is code, so a wrong
classification is a failing unit test.

## Anti-weakening guard (the part that makes it safe)

For every roster task, before and after the edit:

1. `playwright test --list` titles — the after set must be a superset;
2. the spec's source — no `test.skip(`, `test.fixme(`, `.only(`;
3. `expect(` count per changed spec file must not decrease;
4. after the whole phase, the originally failing titles must appear **and pass** in
   the final recorded run at the current delta hash.

A violation reverts the task's paths (archived in `<run>/reverted/`, the 022
pattern) and stops as `e2e_weakened` with the reason list. This is the Donobu
"flag any change that weakens a test" rule and AutoCover's "do no harm" rollback,
implemented where a model cannot talk its way past it.

## Budgets and knobs

| Knob | Default | Why |
| --- | --- | --- |
| `SWARM_E2E_SELF_HEAL` | `1` | off restores 026 behaviour (red suite → fix loop) |
| `SWARM_MAX_INNER_TASKS` | `3` | more than three failures in one task is a broken suite, not a repair |
| `SWARM_MAX_INNER_ROUNDS` | `2` | repair → re-run twice; the second failure set is usually smaller |
| `SWARM_TRIAGE_MODEL` | senior | one call to describe the failure; the table stays code |

All of them also respect the existing per-task wall/cost caps
(`SWARM_TASK_WALL_BUDGET`, `SWARM_MAX_COST_PER_TASK`).

## Failure modes and their stops

| Situation | Stop |
| --- | --- |
| fixture backend down, no `DATABASE_URL`, no browser | `e2e_env` |
| title passed on retry | `e2e_flaky` |
| > `SWARM_MAX_INNER_TASKS` failures | `e2e_roster_overflow` |
| table cannot classify | `e2e_unclassified` |
| a repair deletes/skips/weakens an assertion | `e2e_weakened` |
| rounds exhausted with the suite still red | `needs_human` + `e2e_self_heal.stop` |

## Measurement

- `run.json.e2e_self_heal` per run: class, failed titles, roster size, rounds,
  reverted attempts, stop.
- `make swarm-report`: red-suite runs split by class; how many healed; how many
  ended `e2e_weakened` (should stay 0 — a non-zero is a guard bug, not a model bug).
- `make swarm-bench`: one frozen red-run fixture renders the triage digest and the
  roster with no model call, so the phase's prompt cost is measured like the rest.
