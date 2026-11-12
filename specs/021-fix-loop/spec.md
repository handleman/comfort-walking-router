# 021 Fix Loop — Spec

Control-plane spec (added to `HARNESS_SPECS`): the queue never implements it.

## Problem

020 removed the cheap waste (prompt prefixes, compaction, spill, gate
selection). It did not touch the expensive waste: **the second round**.

Measured over `swarm/runs/` (86 runs, 2026-10-10 → 2026-11-12):

| Fact | Value |
| --- | --- |
| Green runs needing ≥1 fix round | **32 / 54 (59%)** |
| Prompt tokens in `coder:fix*` | **7.27M / 16.3M (44.6%)** |
| p50 wall clock, green without a fix round | **202 s** |
| p50 wall clock, green with ≥1 fix round | **615 s (3.0×)** |
| Fix rounds burned by non-green runs | **60** (8 budget stops, two 6-round reviewer blocks) |
| Last failing gate | `npm lint` 20, `npm check` 12, `pytest` 8, `ruff` 8, `npm test` 7, `mypy` 5 |
| `style_autofix` occurrences | **0 / 86**, including 68 runs after the feature landed |

Three structural causes, from `docs/research/fix-loop-2026.md`:

1. **The deterministic repair path never fires.** It requires the style gate to
   be the *only* red gate, recognises only Prettier and a few scoped ESLint
   rules, and runs after QA instead of before it. A mechanical formatting
   failure reaches a model 20 times in this history.
2. **Nothing writes the failing test from the acceptance criteria.** The coder
   writes test and implementation in one trajectory, so a wrong assumption is
   encoded twice. The 2026 evidence says a tests-first phase with an independent
   test author cuts iterations ~40–50%, and that a *weak* test author is worse
   than no test at all.
3. **The loop cannot tell a code round from a verdict/evidence round.** Four
   runs spent 1–6 rounds while QA produced no grounded verdict; `run.json` has
   no per-round cause. 017 (self-check) and 019 (verifier) have one run of data
   between them, so their cost/benefit is unmeasured.

## Goal

Cut the fix-round rate and the tokens/wall clock it costs, **without lowering
the green rate**, and make every later harness change (parallelism, earned
autonomy) judgeable on outcomes rather than on prompt characters.

## Scope

- An outcome replay suite (5–8 frozen cases) and a baseline snapshot.
- Per-round fix telemetry: cause, report shape, round outcome, 017/019 hit rate.
- Deterministic repair before QA (formatting and fixable lint) with an off switch.
- A tests-first A/B with a separate test-author role, frozen tests, off by default.
- An AC-aware coder prompt A/B, off by default.
- Repair-budget and checkpoint-preservation policy; stale-evidence refusal.
- Measurement, docs, knobs, and a keep/revert decision for each A/B.

## Non-goals

- Parallel micro-steps or concurrent workers (022).
- Earned auto-merge, risk classes, post-merge loop (023).
- A new orchestrator or a framework migration (ADR-012 stays as recorded).
- Weakening QA's ownership of green or the 019 verifier's read-only contract.

## Acceptance criteria

- **AC-1 — Outcome suite.** `make swarm-replay` runs a frozen set of 5–8 cases
  from `swarm/bench/corpus/` through the 020 T7 live path (worktree at
  `green_sha^`, current harness, pinned models, no commit) and records per case:
  green/not, wall clock, prompt/cached tokens, cost, fix rounds and failing
  gates. A committed `swarm/bench/replay_baseline.json` snapshots the first run.
  `SWARM_REPLAY_CASES` selects the set; `SWARM_REPLAY_OFF=1` runs the same cases
  with the 021 behaviours off for an A/B. The suite is opt-in (models required)
  and never part of `make swarm-test`.

- **AC-2 — Fix telemetry.** Every fix round records `fix_cause`
  (`type` / `lint` / `test` / `scenario` / `verdict` / `evidence` / `other`),
  the failing gate set, the round's delta signature and whether it changed
  anything, in `run.json.fix_rounds_detail`. The cause is derived mechanically
  from the report (gate + key lines), never from model prose. `make swarm-report`
  aggregates the cause distribution, the share of rounds that changed nothing,
  and the 017 self-check / 019 verifier hit rate (a phase "hit" when it found a
  defect that the following QA round confirmed).

- **AC-3 — Deterministic repair before QA.** Formatting and `--fix`-able lint
  failures are repaired by the harness after the micro-steps and after every fix
  round, before QA runs; the affected gate is re-checked and recorded. A
  formatting-only failure never reaches a coder. The "sole red gate" condition
  is removed, and the recogniser covers unscoped ESLint rules that `--fix` owns
  plus Prettier alongside other red gates. `SWARM_STYLE_PRE_QA=0` restores the
  020 behaviour; QA remains the only gate executor and the repair cannot make a
  run green.

- **AC-4 — Tests-first A/B.** `SWARM_TESTS_FIRST=1` adds one phase between the
  plan and the implementation steps: a **Test Author** crew (separate role, no
  write access to the implementation files) writes the failing test that encodes
  the referenced acceptance criteria, the harness records its red state and
  freezes the file(s), and the implementation steps must make it pass without
  editing the frozen tests. Default `0`; the suite decides whether it ships, and
  the result is recorded either way. A test-author round that cannot produce a
  failing test stops the phase, never the task.

- **AC-5 — AC-aware coder prompt A/B.** `SWARM_CODER_ACS=1` includes the
  referenced AC paragraphs in the coder prefix (020 T2 excluded them to keep the
  prefix lean). Default `0`; the outcome suite compares it with the current
  prompt on the same cases and the result is recorded.

- **AC-6 — Repair budget and checkpoint preservation.** The round cap stays 3
  unless the suite shows a gain at 4. A round whose evidence is stale (the delta
  did not change since the previous QA run, or QA produced no grounded verdict)
  is classified as `verdict`/`evidence` and does not consume a code round. The
  best verified delta is preserved as a checkpoint (`run.json.best_delta`) so a
  later round cannot regress a previously passing gate silently.

- **AC-7 — Verification ROI.** For each run, record whether 017 caught something
  (a red static check that the coder then fixed) and whether 019 blocked a
  scenario QA would have passed. `make swarm-report` prints both rates over the
  selected window. If a phase's hit rate is near zero over the suite, the spec
  records a concrete tune-or-remove follow-up; it is not removed inside 021
  without that measurement.

- **AC-8 — Knobs and defaults.** Every new behaviour has a documented off switch
  (`.env.example` + `swarm/README.md`): `SWARM_REPLAY_CASES`, `SWARM_REPLAY_OFF`,
  `SWARM_STYLE_PRE_QA`, `SWARM_TESTS_FIRST`, `SWARM_CODER_ACS`. Disabling every
  knob restores the 020 behaviour, and `make swarm-test` covers both paths.

- **AC-10 — Coder-prompt strictness A/B.** `SWARM_CODER_LOOSE=1` (default 0)
  relaxes only the step-crew mechanics: up to 8 tool calls instead of 5,
  `max_iter` 8 instead of 6, an explicit "continue with `start_line`" rule for a
  truncated read, and "re-read only when the file changed since your last read"
  instead of "never read the same file twice". Scope, the real-API rule and the
  no-gates rule are unchanged. `SWARM_PLAN_MAX_STEPS` (default 8) lets the
  planner choose the fewest coherent steps for a small task. The outcome suite
  runs the same cases strict vs loose and with a stronger coder pin, so a result
  is attributed to the prompt, the plan granularity or the model — not guessed.
  The default stays strict until the suite shows a win.

- **AC-11 — Verifier stability.** The 019 verifier may not re-litigate its own
  correction. Its prompt forbids prescribing how a test mocks, structures
  fixtures or names cases — it requires the behaviour the AC names. When a block
  arrives after a **landed** correction and names the same file as the earlier
  finding, the verdict is unstable: it becomes a warning (`verifier.overridden`)
  and QA's gates decide, because a subjective test-design preference must not
  make a run unconvergeable. When the correction changed nothing, the block is
  `stalled` (a coder failure) and the run stops as `verifier_blocked`. The
  stability record (`finding_files`, `corrections`, `corrected`, `unstable`,
  `overridden`, `stalled`) lands in `run.json.verifier`.

- **AC-12 — A step must land its file.** A plan step of the form
  `STEP n: <file> — <action>` is an edit, not a description: after the step
  crew runs, the harness checks the step's target file is in the run delta. If
  it is not (the common small-model failure of pasting the file into the answer
  instead of calling Repo Create), the step counts as a failed attempt and is
  retried, and the senior escalation path is available exactly as for an
  exception. `run.json.steps[].landed` records it. The verifier's own
  correction pass follows the same rule: a correction that changes nothing is
  `stalled` (a coder failure), not `unstable` (a verifier contradiction).

- **AC-9 — Measured result.** The outcome suite runs before and after; the
  before/after table lands in `docs/research/fix-loop-2026.md` and `changelog.md`.
  Targets: fix-round rate **59% → ≤35%**, `coder:fix*` prompt tokens **−40%**,
  p50 wall clock for fix tasks **615 s → ≤400 s**, and the green rate **not
  lower** than the 020 baseline. A target missed is recorded with its number and
  reason; an A/B that loses is reverted, not kept behind a flag.

## Evidence

- `docs/research/fix-loop-2026.md` — measured anatomy, market patterns, backlog.
- `swarm/runs/` (86 runs), `swarm/report.py`, `swarm/style.py`,
  `swarm/flow.py::_autofix_style`, `specs/020-harness-efficiency/`.
- Market: tests-first (~40–50% fewer iterations), diminishing returns after 3–4
  repairs, stale-evidence harm, ExecCritic's independent test author, Google
  AutoRepair's deterministic final validation (links in the investigation).

## Success definition

The outcome suite shows the fix rate and its cost down while green holds. The
phase does not claim a win from a cheaper prompt; it has to show fewer rounds on
the same tasks.
