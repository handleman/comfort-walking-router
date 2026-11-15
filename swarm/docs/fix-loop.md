# The fix loop (021)

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Tests-first (021 T4, opt-in A/B)
`SWARM_TESTS_FIRST=1` adds one phase between the plan and the implementation: a
`Test Author` crew writes one failing test per referenced acceptance criterion.
- The author has no shell and the write tools are `test_only`: it cannot edit
  implementation files or run a gate.
- The harness runs the test under its own role (`harness-tests-first`), records
  `run.json.tests_first` (`files`, `command`, `red`, `output`, `failed`), and
  **freezes** the files by hash. Step crews get a note naming them, and the tool
  layer refuses an edit to a frozen test.
- A test that already passes is a failed phase (`failed: the authored test
  already passes`), never a win; the flow continues normally.
- Default off because a weak test author can be worse than no test (ExecCritic);
  `make swarm-replay` with `SWARM_TESTS_FIRST=1` is how it earns being on.

## Deterministic repair before QA (021 T3)
Formatting is mechanical, so it never reaches a model. `SWARM_STYLE_FIX_COMMAND`
is a `;`/newline-separated list (this repo can run
`npm --prefix frontend run lint:fix` and `ruff check --fix .`), and the harness
runs every command **before each QA round** whenever the run's delta is
non-empty. It then reverts any file that is not part of the run delta (012
attribution) and records `run.json.style_autofix` (`gate: "pre-qa"`, commands,
files, reverted, output). `is_style_failure` now also recognises `--fix`-owned
ruff codes (I001, F401, whitespace) next to Prettier and the fixable scoped
ESLint rules; hard failures (syntax, type mismatch, redefinition) stay with the
coder. The 017 self-check formats its own static failures the same way, and its
resolved command list is recorded in `run.json.self_check.commands`.
`SWARM_STYLE_PRE_QA=0` restores the 020 behaviour (format only when a sole style
gate fails, after QA).

## Repair budget and verification ROI (021 T6/T7)
- `SWARM_MAX_FIX_ROUNDS` (default 3) caps **code** rounds. A round whose cause
  is `verdict` or `evidence` (see below) does not consume that budget; it has
  its own cap of 1, so a QA that never grounds a verdict cannot loop.
- `run.json.best_delta` records the delta that passed the most gates
  (`delta`, `green_gates`, `total_gates`, `gates`, `round`), so a later round
  cannot silently regress a gate that once passed. Green still requires every
  gate at the final delta.
- `self_check.detected` / `self_check.hit` (017) and `verifier.hit` /
  `hit_basis` (019) record whether each phase found something: 017 hits when a
  red static check is then fixed in the phase; 019 hits on a grounded block.
  `make swarm-report` prints both rates next to the repair causes.

## Fix telemetry (021 T2)
Every repair round is labelled mechanically from the report the coder received —
never from model prose — and recorded in `run.json.fix_rounds_detail`:

| cause | when |
| --- | --- |
| `scenario` | the 019 verifier blocked and its corrections drove the round |
| `verdict` | QA produced no grounded verdict (unknown / ungrounded block) |
| `evidence` | no gate evidence, or the round changed nothing (stale delta) |
| `type` | a type-check gate is failing (outranks a failing test) |
| `test` | a test gate is failing with assertion/failure lines |
| `lint` | only lint/format gates are failing |
| `other` | anything else |

Each entry also carries `phase` (`fix`/`senior`/`verify`/`selfcheck`), the
failing gates, `changed`, `tokens` and `seconds`. `make swarm-report` prints the
cause distribution, how many rounds changed nothing, and the 017/019 hit rates —
the last two are what 021 T8 uses to decide what to keep.

## Coder strictness and plan size (021 T10)
Two A/Bs, both off/at the strict default until the suite shows a win:

- `SWARM_CODER_LOOSE=1` relaxes **only** step mechanics: 8 tool calls instead of
  5, `max_iter` 8 instead of 6, "continue with the `start_line` the note names"
  instead of "never read the same file twice", and re-read only when the file
  changed. Scope, the real-API rule and the no-gates rule are unchanged.
- `SWARM_PLAN_MAX_STEPS` (≤ 8) asks the planner for that many micro-steps and to
  use the fewest coherent steps for a small task. `steps_usable` still caps at 8.

## Repair routing (021 T14)
- The first code fix round uses the coder model. A **second** round is a stuck
  loop, so it runs on the senior crew (`senior:fixN`, `build_senior_crew`).
- Every 019 verifier correction runs on the senior step crew
  (`senior:verifyN`, `build_senior_step_crew`) with the findings as the error
  context: the scenario is already stuck, so a stronger one-shot pass is cheaper
  than another coder round.
- Role prefixes drive fallback mapping, so `senior:*` roles degrade to the
  senior fallback, never the coder's.

## Anti-loop guards (Qwen-9B wanders: re-reads files, blows 262k ctx)
- `TrimmedFileReadTool`: observations capped at 3000 chars (re-read via `start_line`/`line_count`).
- `FullFileReadTool`: the scenario verifier's read (019), capped by `SWARM_VERIFY_READ_CHARS`
  (default 60000); a bigger file is reported by name/size with the next `start_line`, never
  silently returned as a head. Coders keep the trimmed read.
- No `DirectoryReadTool`: `ls` via Guarded Shell has fewer wandering branches.
- Task prompts carry hard loop rules (≤6 tool calls, never re-read, answer from observations).
- `max_iter` 10/10/5 + 1 fix round max. Still stuck → `needs_human`.
