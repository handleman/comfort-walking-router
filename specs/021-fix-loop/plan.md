# 021 Fix Loop — Plan

Status: proposed. References `specs/021-fix-loop/spec.md` AC-1–AC-9 and
`docs/research/fix-loop-2026.md`.

## Approach

Measure the loop, make the mechanical class disappear, then test the one
behavioural bet (tests-first) on outcomes. Every change is a knob whose `0`
value is the 020 behaviour, and every A/B is decided by the replay suite, not by
the offline bench.

```
T1  outcome suite + baseline (5–8 cases)
      │
      ├─ T2  fix telemetry (cause, report shape, round outcome)
      │        │
      │        ├─ T3  deterministic repair before QA (R1/R2/R7)
      │        │
      │        ├─ T4  tests-first A/B, separate test author (R3)
      │        │
      │        ├─ T5  AC-aware coder prefix A/B (R4)
      │        │
      │        └─ T6  repair budget + checkpoint preservation (R6)
      │                 │
      │                 ├─ T7  verification ROI (017/019) + report view
      │                 │
      │                 └─ T8  before/after on the suite, keep/revert each A/B
      │                          │
      └──────────────────────────┴─ T9  docs, knobs, HARNESS_SPECS, gates
```

T1 and T2 come first: without an outcome baseline and a cause label, every later
number is anecdote. T3 is the highest-confidence win (zero model work for a
mechanical class). T4/T5 are bets and are kept only on a measured win. T6 is
policy and must not change the green definition. T7 is the "does the harness
itself pay for itself" audit.

## T1 — the outcome suite

`swarm/bench/replay.py` (or extend `swarm/bench/live.py`):

- `run_suite(cases: list[str], *, off: bool) -> dict` reuses `live.run_case` for
  each case, sequentially (one task at a time, the single-run lock is inside the
  worktree), and aggregates: green count, mean/median wall clock, prompt and
  cached tokens, cost, fix rounds, failing gates.
- `swarm/bench/replay_baseline.json` snapshots the first run with the case list,
  model pins (hashes of names, not keys), harness commit and date.
- `make swarm-replay` (all cases) and `make swarm-replay CASE=<id>` (one);
  `SWARM_REPLAY_OFF=1` sets the 020 switches (`SWARM_STYLE_PRE_QA=0`,
  `SWARM_TESTS_FIRST=0`, `SWARM_CODER_ACS=0`, `SWARM_CONTEXT_COMPACT` left on) so
  the same cases measure the old loop.
- Cases: start with the smallest four (`004-weather-sun-T2`, `005-saved-routes-T2`,
  `006-comfort-plus-T3`, `010-e2e-playwright-T5`), add backend + frontend so the
  lint/type classes are represented. Bound: 8 cases, < 45 min per suite run.

The suite is opt-in (models, minutes). `make swarm-test` covers the aggregation
and the off-switch mapping with a fake runner.

## T2 — fix telemetry

- `swarm/fixcause.py`: `classify(report, changed_before, changed_after) -> dict`
  with `cause` from the failing gates and their key lines:
  - `lint` — the only failing gates are lint/format commands;
  - `type` — a type-check gate is failing;
  - `test` — a test gate is failing with assertion/failure lines;
  - `scenario` — the 019 verifier blocked and its corrections drove the round;
  - `verdict` — QA returned no grounded verdict (`unknown`, ungrounded block);
  - `evidence` — missing/stale gate evidence, or the delta did not change;
  - `other`.
- Flow records `state.fix_rounds_detail.append({...})` per round: cause, gates,
  `changed` (bool), `delta` signature, `tokens`, `seconds`, `phase`
  (`fix`/`senior`/`selfcheck`/`verify`).
- `make swarm-report` gains a "fix causes" section and a "verification" section.
  No model calls: the classification is mechanical, with QA's `review_text` used
  only as a last-resort keyword fallback (labelled `other` when ambiguous).

## T3 — deterministic repair before QA

- Move the style repair from "after QA, sole red gate" to "after the steps and
  after every fix, before QA": run `SWARM_STYLE_FIX_COMMAND`, then re-run the
  affected lint/format gate under the harness role, and record
  `run.json.style_autofix` every time (including "no change").
- Broaden `style.is_style_failure`: Prettier markers anywhere in a lint tail;
  unscoped ESLint rules that `eslint --fix` owns (prefer-const, semi, quotes,
  indent, comma-dangle, …); keep the hard markers (syntax, cannot find name,
  type mismatch, duplicate identifier) as non-style.
- Audit the 017 static set (`SWARM_SELF_CHECK_COMMANDS`): it must include the
  frontend type check where the project has one, because `npm run check` is the
  #2 failing gate. Record the resolved command list in `run.json.self_check`.
- `SWARM_STYLE_PRE_QA=0` restores the 020 behaviour (repair only when it is the
  sole gate, after QA).
- Trust surface unchanged: the repair is a write by the harness inside the run
  scope, the gate is re-run and recorded, and QA still decides green.

## T4 — tests-first A/B

`build_test_author_crew(spec_dir, task, ac_text, target_files)`:

- Role "Test Author"; tools: read + create + edit, **no shell, no gates**; it may
  only write files under the test paths for the task (`tests/**`,
  `frontend/**/*.test.ts`, `frontend/e2e/**`), enforced by a path guard, and it
  never edits implementation files.
- The prompt carries the brief and the referenced AC paragraphs (not the plan
  steps) and asks for one failing test per AC, with the exact command that shows
  it red.
- The harness runs the test command under its own role (not QA evidence), records
  `run.json.tests_first = {files, red: bool, command, output_tail}` and freezes
  the files (hash recorded). Implementation steps are told the tests are frozen.
- If the test is not red, the phase records `tests_first.failed` and continues
  with the normal flow; it never blocks the task.
- `SWARM_TESTS_FIRST=0` (default) skips the phase entirely.

Risk: a weak test author encodes a wrong behaviour and makes the loop worse
(ExecCritic). Mitigation: the A/B on real cases, and the 019 verifier still
checks the scenario end to end.

## T5 — AC-aware coder prefix A/B

- `prompts.stable_prefix(..., kind="step")` gains `include_ac` (env
  `SWARM_CODER_ACS`, default 0). When on, the coder prefix carries the referenced
  AC paragraphs (bounded by the existing `MAX_AC_CHARS`).
- The bench records `prefix_sha256` per configuration, so the two prompts are
  distinguishable; the outcome suite decides.
- Default stays off until the suite says otherwise.

## T6 — repair budget and checkpoint preservation

- Keep `MAX_FIX_ROUNDS=3`; make the cap a knob (`SWARM_MAX_FIX_ROUNDS`) so the
  suite can test 4 without a code edit.
- Classify a round as `verdict`/`evidence` (T2) when the delta is unchanged or
  QA gave no grounded verdict: it does not count against the code-round budget
  but is capped separately (`MAX_VERDICT_ROUNDS=1`, existing repair path).
- Preserve the best verified delta: when a round passes a gate that later goes
  red, record the earlier delta hash and its gates in `run.json.best_delta`, and
  never merge a delta that regresses it without a human.
- No change to the green definition: QA evidence still decides.

## T7 — verification ROI

- 017: `self_check.hit` when the pre-QA static check was red and the following
  QA round was green on that gate (the coder fixed it before QA).
- 019: `verifier.hit` when the verifier blocked and QA's next round confirmed the
  finding (the run did not reach QA green without the correction), or when a
  correction step touched a file the QA report later named.
- `make swarm-report`: phase, runs, hits, hit rate, tokens spent in that phase.
- If a phase's rate is near zero, the result is recorded with a recommended
  action; removal is a separate decision (never silent).

## T8 — measurement and keep/revert

Run the suite three times where practical:

| Run | Configuration |
| --- | --- |
| baseline | 020 behaviour (all 021 knobs 0) |
| mechanical | + T3 deterministic repair |
| tests-first | baseline + `SWARM_TESTS_FIRST=1` |
| AC prompt | baseline + `SWARM_CODER_ACS=1` |

Write the table in `docs/research/fix-loop-2026.md` (case, green, wall clock,
tokens, fix rounds, cause mix) and decide each A/B. A variant that lowers green
is reverted and recorded as a negative result.

## T9 — docs and controls

- `HARNESS_SPECS += ("021-fix-loop",)`.
- `swarm/README.md`: the suite, the telemetry fields, the repair-before-QA rule,
  the tests-first phase, the knobs, and how to read `fix_rounds_detail`.
- `AGENTS.md`: one state line and one lesson (measure rounds on outcomes; keep or
  revert an A/B on the suite, not on the offline bench).
- `docs/roadmap.md`: mark 021 implemented; record 022 (parallel) and 023 (earned
  autonomy) with the decision date.
- `changelog.md`: the measured result and the keep/revert decisions.
- `make swarm-test`, `ruff check .`, `mypy app tests`.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Formatting repair hides a real lint rule | Only Prettier and `--fix`-owned rules are repaired; the gate is re-run and the tail recorded; hard markers never qualify |
| Test author encodes a wrong behaviour | Separate role, frozen tests, A/B on real cases, 019 still verifies the scenario; keep only on a win |
| Freezing tests blocks a legitimate implementation change | The phase records `tests_first.failed` and the flow continues; freezing applies only inside that task |
| The suite is slow or flaky | 5–8 cases, sequential, models pinned, < 45 min; a flaky case is dropped with a note |
| Telemetry becomes a second source of truth | `fix_cause` is a label on top of the existing evidence, never an input to green |
| An A/B win is noise on 5 cases | Require the direction to hold on every case pair, and report the per-case table, not only the mean |
