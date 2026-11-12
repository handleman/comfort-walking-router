# 021 Fix Loop — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [x] T1 (AC-1): add the outcome replay suite — `make swarm-replay` runs 5 frozen corpus cases through the 020 T7 live path (worktree at `green_sha^`, current harness, pinned models, no commit), aggregates green/wall clock/tokens/cost/fix rounds/failing gates, and writes `swarm/bench/replay_baseline.json` (first snapshot at T8, with `--off` so the baseline is the 020 loop). `SWARM_REPLAY_CASES` selects the set; `SWARM_REPLAY_OFF=1` maps every 021 knob to its 020 value for the A/B.
  Evidence: `swarm/bench/replay.py`, `Makefile`, `swarm/tests/test_replay.py`; baseline at `swarm/bench/replay_baseline.json` (T8).
- [x] T2 (AC-2): record per-round fix telemetry — `swarm/fixcause.py` classifies each round mechanically (`type`/`lint`/`test`/`scenario`/`verdict`/`evidence`/`other`) from the report's failing gates and key lines; the flow appends cause, gates, phase, changed, tokens and seconds to `run.json.fix_rounds_detail` for fix, senior, verifier-correction and self-check rounds; `make swarm-report` aggregates causes, phases, no-change rounds and verification hits.
  Evidence: `swarm/fixcause.py`, `swarm/flow.py`, `swarm/report.py`, `swarm/tests/test_fixcause.py`.
- [x] T3 (AC-3): repair deterministically before QA — the configured fix commands (now a `;`-separated list, so frontend and Python formatters both run) execute before every QA round when the delta is non-empty; the formatter reverts foreign files by run-delta attribution only; `is_style_failure` recognises `--fix`-owned ruff codes (I001/F401/whitespace) alongside Prettier and fixable scoped ESLint rules; the 017 static set already covers the frontend type check (`npm run check`) and records its resolved commands. `SWARM_STYLE_PRE_QA=0` restores 020.
  Evidence: `swarm/style.py`, `swarm/flow.py`, `swarm/tests/test_style.py`.
- [x] T4 (AC-4): tests-first as an A/B — a separate `Test Author` crew writes one failing test per referenced AC, restricted to test paths and frozen by hash (the write tools refuse a frozen test); the harness runs the test under its own role, records `run.json.tests_first`, and the implementation steps are told the tests are frozen. `SWARM_TESTS_FIRST=0` by default; a non-red test records a failed phase and continues.
  Evidence: `swarm/crew.py::build_test_author_crew`, `swarm/tests_first.py`, `swarm/flow.py`, `swarm/tools_guarded.py`, `swarm/tests/test_tests_first.py`.
- [x] T5 (AC-5): AC-aware coder prefix as an A/B — `SWARM_CODER_ACS=1` puts the referenced AC paragraphs back into the coder prefix (bounded by `MAX_AC_CHARS`), recorded in the bench prefix hash; default off.
  Evidence: `swarm/prompts.py`, `swarm/tests/test_prompts.py`.
- [x] T6 (AC-6): repair budget and checkpoint preservation — `SWARM_MAX_FIX_ROUNDS` (default 3), `verdict`/`evidence` rounds classified separately and capped at 1 without consuming a code round, and `run.json.best_delta` records the delta with the most green gates so a later round cannot silently regress one.
  Evidence: `swarm/flow.py`, `swarm/tests/test_autoloop.py`.
- [x] T7 (AC-7): verification ROI — 017 records `self_check.detected/hit` (red then fixed in the phase) and 019 records `verifier.hit` + `hit_basis` (grounded block with corrections, or ended blocked); `make swarm-report` prints runs/hits per phase. A near-zero rate becomes a recorded recommendation, never a silent removal.
  Evidence: `swarm/flow.py`, `swarm/report.py`, `swarm/tests/test_selfcheck.py`, `swarm/tests/test_verify.py`.
- [ ] T8 (AC-9): measure and decide — run the suite for baseline, mechanical repair, tests-first and AC-prompt variants; write the per-case before/after table into `docs/research/fix-loop-2026.md` and `changelog.md`; keep a variant only if it lowers the fix rate without lowering green, otherwise revert and record the negative result.
  Evidence: `docs/research/fix-loop-2026.md` (results), `changelog.md`, `swarm/bench/replay_baseline.json`.
- [ ] T9 (AC-8): close the loop — add `021-fix-loop` to `HARNESS_SPECS`, document every knob in `.env.example` and `swarm/README.md`, update `AGENTS.md`/`docs/roadmap.md`, and run `make swarm-test`, `ruff check .`, `mypy app tests`.
  Evidence: `swarm/flow.py::HARNESS_SPECS`, `.env.example`, `swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`.

## Decisions (2026-11-12)

- **Next phase is the fix loop, not parallelism.** 020 measured the cheap waste;
  44.6% of prompt tokens and a 3× wall-clock penalty sit in `coder:fix*`.
  Parallelism multiplies a 59%-repair loop, and earned autonomy multiplies its
  mistakes; both wait until the loop is cheaper.
- **Outcome suite inside 021.** The offline bench measures characters; the suite
  measures green/cost/time/rounds. It is how 022 and 023 will be judged.
- **Tests-first is an A/B, not a default.** ExecCritic's evidence that a weak
  test author performs worse than no test makes a default-on switch unsafe.
- **Deterministic repair is not a trust change.** Formatting and `--fix`-owned
  lint are mechanical; the gate is re-checked and recorded, QA still owns green.
- **Verification phases are measured, not assumed.** 017/019 have one run of
  data between them; 021 records hit rates before removing or duplicating them.

## Phase 021 evidence

`swarm/runs/` (86 runs): 59% of green runs need a fix round; 44.6% of prompt
tokens are `coder:fix*`; p50 202 s without a fix round vs 615 s with one; the
last red gate is frontend lint/check in 32 of 48 placed runs; `style_autofix`
fired 0 times. Full anatomy, market patterns and the opportunity backlog:
`docs/research/fix-loop-2026.md`.
