# The fix loop: where the tokens actually go (2026-11)

Status: investigation for `specs/021-*`. Read-only analysis of `swarm/runs/`
(86 runs, 2026-10-10 → 2026-11-12) plus a focused market check on repair loops.
It complements `docs/research/dark-factory-market-2026.md`: that document asked
*which harness capabilities are missing*; this one asks *why a task needs a
second round at all*.

## Why this exists

020 removed the cheap waste: prompt prefix stability, context compaction,
gate-log spilling, gate selection. It did not touch the expensive waste.

Measured over the same history:

| Fact | Value |
| --- | --- |
| Green runs that needed ≥1 fix round | **32 of 54 (59%)** |
| Prompt tokens spent in `coder:fix*` roles | **7.27M of 16.3M (44.6%)** |
| Wall clock, green runs without a fix round (p50) | **202 s** |
| Wall clock, green runs with ≥1 fix round (p50) | **615 s (3.0×)** |
| Fix rounds burned by non-green runs | **60** (8 budget stops had 3–4; two reviewer-blocked runs had 6) |

Fix rounds are not a quality detail. They are the largest single line in the
token bill, the reason the p90 tail exists, and the state in which most human
stops happen. A phase that halves them is worth more than any of the 020
changes, and it makes 022 (parallelism) and 023 (earned autonomy) safer:
parallelising a 59%-repair loop multiplies rework, and automating merges on top
of it multiplies risk.

## What the history says about the cause

### The failing gate is usually frontend

Last failing gate among all runs, from `run.json.qa_report` / `evidence.gates`:

| Gate | Runs where it is the last red gate |
| --- | --- |
| `npm --prefix frontend run lint` | **20** |
| `npm --prefix frontend run check` (svelte-check) | **12** |
| `pytest -q` | 8 |
| `ruff check .` | 8 |
| `npm --prefix frontend test -- --run` | 7 |
| `mypy app tests` | 5 |

Where a green run's last report is analyzable (20 of 32), the shapes are:

| Shape | Runs |
| --- | --- |
| sole `npm run lint` | 6 |
| `npm run check` + `npm run lint` | 3 |
| sole `pytest` / sole `ruff` / mixed backend | 5 |
| `check` + `test`, `test` alone, others | 3 |

So the loop is not dominated by deep semantic bugs. It is dominated by the
frontend verification pair: formatting/lint and type checking.

### The deterministic repair path never fires

`swarm/style.py` can repair formatting without a coder round, and
`run.json.style_autofix` records every time it does. In 86 runs — including 68
after the feature landed — **it fired zero times**.

The reason is structural, not bad luck:

- `_autofix_style` only runs when the style gate is the **only** red gate
  (`style_gate` requires `len(failing) == 1`). A lint+check round never
  qualifies, even when the lint half is pure formatting.
- `is_style_failure` recognises Prettier markers and a small set of *scoped*
  ESLint rules (`@scope/rule`). `npm run lint` is `eslint . && prettier
  --check .`, so an unscoped rule (e.g. `no-unused-vars`) yields no rule match
  and the tail is not treated as style even when Prettier would also fail.
- The repair runs after QA, not before it: the coder has already spent a round
  by the time the formatter is considered.

That is the clearest single defect the data contains: a mechanical class of
failure reaches a model, 20 times.

### Tests encode the coder's own assumptions

Several of the long repairs are assertion churn: the test and the
implementation are written in the same trajectory, so a wrong assumption is
encoded twice (014-T7 shipped a client reading `results` while the pinned plan
said `suggestions`; 007-T9's test declared a `tick` the provider never had).
The 019 verifier catches "the pieces do not connect" after the fact, but it
does not prevent the first wrong test. Nothing in the loop writes the failing
test *from the acceptance criteria* before the implementation exists.

### Evidence quality and verdict gaps

Four runs ended in `reviewer_blocked` / `reviewer_no_verdict`, two of them after
**6** fix rounds: the loop kept spending rounds while QA never produced a
grounded verdict. 007's lessons fixed part of this (verdict repair, report key
lines), and 020 T4/T6 made the report smaller and single-form, but the history
predates those changes. The point for 021 is measurement: we cannot currently
tell a *code* fix round from a *verdict/evidence* fix round in `run.json`.

### We have no data on the new verification phases

017 (self-check) appears in **1** run and 019 (verifier) in **0** — both landed
at the end of the window. Their cost is one extra crew call per task and their
benefit is unmeasured. Task 021 must instrument the hit rate, because "remove
work the loop does not need" applies to the harness's own phases too.

## What the market does about repair loops

The 2026 literature is consistent on four points, and all four map to this
harness:

1. **Tests first, and written independently of the patch.** A tests-first phase
   (write the failing test from the requirement, then implement) reports
   ~40–50% fewer iterations and roughly half the tokens versus a naive loop
   ([tests-first agent loop, 2026-01](https://micheallanham.substack.com/p/the-tests-first-ai-agent-loop-for);
   [Augment, 2026-07](https://www.augmentcode.com/guides/how-agents-close-build-test-fix-loop)).
   ExecCritic's finding is the important nuance: when the same trajectory writes
   both test and patch, both can agree on a wrong behaviour; an independent test
   author lifts the resolved rate, while a weak test author *lowers* it below no
   test at all ([ExecCritic, 2026](https://arxiv.org/pdf/2609.09133v1)).
2. **Repair budgets have diminishing returns.** The first 3–4 repair iterations
   deliver most of the gain; later ones are marginal, and orchestration/feedback
   design matters more than the model
   ([Is Three the Magic Number?, 2026-10](https://doi.org/10.1145/3832783.3834547)).
3. **Stale evidence is harmful; verified checkpoints should be preserved.**
   Forced revision with *stale* traces hurts previously-correct solutions;
   current evidence helps. The proposed discipline is a typed revision contract
   with an evidence gate and checkpoint preservation
   ([Looping Is Not Reliability, 2026-07](https://ar5iv.labs.arxiv.org/html/2607.24604)).
4. **Validate deterministically before presenting a fix.** Google's AutoRepair
   runs a generate-and-validate loop with a bounded tool/runtime budget and a
   final deterministic validation, because a model's own claim of success is not
   evidence ([AutoRepair, 2026-10](https://arxiv.org/html/2610.07289v1)).

Our harness already has (2)'s bound (`MAX_FIX_ROUNDS=3`), (4)'s final
validation (QA-only evidence, `shell_log.jsonl`), and (3)'s "current evidence"
rule partly (evidence hash). It does **not** have (1), and its deterministic
repair is narrower than the data requires.

## Opportunity backlog

Impact is on fix rounds / tokens / wall clock; effort S ≤ 1 day, M ≤ 1 week,
H > 1 week; risk is "new trust surface" or "gameable check".

| ID | Opportunity | Evidence | Impact | Effort | Risk |
| --- | --- | --- | --- | --- | --- |
| **R1** | **Format before QA, every round** — run the formatter after the steps and after each fix, then re-check; drop the "sole red gate" condition | `style_autofix` fired 0/86; lint is the #1 failing gate | High | S | Low |
| **R2** | **Deterministic-repair coverage** — recognise unscoped ESLint rules that `--fix` owns and Prettier failures alongside other red gates; never send those to a model | 20 lint-fail runs, 6 sole-lint shapes | High | S–M | Low |
| **R3** | **Tests-first phase** — a red test step derived from the ACs, written by a *test author* role separate from the implementer, frozen before the implementation steps | 40–50% fewer iterations in trials; ExecCritic on independent test authoring | High | M–H | Medium |
| **R4** | **AC-aware coder prefix (A/B)** — 020 T2 excluded AC paragraphs from coder prompts for cost; test whether they cut rounds | The "green but wrong" class (014) | Med | S | Low |
| **R5** | **Per-round fix telemetry** — `fix_cause` (type/lint/test/scenario/verdict/evidence), report shape, and 017/019 hit rate in `run.json`; `make swarm-report` aggregates | Today cause is inferred from prose; 017/019 unmeasured | High (enabler) | S | Low |
| **R6** | **Repair budget + checkpoint preservation** — stop at 3–4, keep the best verified delta, never retry from stale evidence | Diminishing returns after 3–4; stale traces harm | Med | M | Low |
| **R7** | **Static-check coverage audit** — confirm the pre-QA self-check runs the frontend type check as well as lint; fix the gap if not | `check` is the #2 failing gate | Med | S | Low |
| **R8** | **Contract pinning check** — one source per field, asserted before QA (019 already checks "contract and code agree"; make it a typed finding) | 014-T1's three schemas | Med | M | Medium |
| **R9** | **Outcome replay suite** — extend 020 T7 from one case to 5–8, on/off A/B, scoring green/cost/time/fix rounds | 020 T8 needed a live run; chars are not outcomes | High (enabler) | M | Low |

### The 021 baseline replay: the coder, not the verifier

The first 021 baseline run (five cases, `--off`, local `ollama/swarm-coder`)
stopped after three cases because the tool session died; the three completed
cases are unambiguous:

| Case | Status | Time | Prompt tokens | Fix rounds | Verifier |
| --- | --- | --- | --- | --- | --- |
| 004-weather-sun-T2 | `needs_human` / `verifier_blocked` | 983 s | 180k | 0 | 7 → 3 findings |
| 005-saved-routes-T2 | `needs_human` / `verifier_blocked` | 936 s | 188k | 0 | blocked |
| 006-comfort-plus-T3 | `needs_human` / `verifier_blocked` | 1287 s | 404k | 0 | 2 rounds |

006 is the clearest: the coder wrote `tests/test_route_toggles.py` as a
**truncated file** (9 lines, a partial `def _build_route_response(start: str`).
The 017 self-check was red, the coder's repair made the truncation *parse* —
after which `mypy`, `ruff`, `svelte-check` and lint were all green — and the 019
verifier then correctly blocked because the file contained **no test functions**.
The correction step could not fix it, and the run ended `needs_human` without a
single QA gate execution.

That is not the verifier being strict; it is the coder under-implementing. Two
consequences for 021: the suite baseline needs a **capable coder pin** before it
can measure a harness change (otherwise every variant is red for the same
capability reason), and a truncated/no-test file is a **deterministic defect** the
harness can name for free (`swarm/artifacts.py`, added in T10) instead of paying
a verifier round for it.

### The report was lossy, and the coder could not converge

The fourth replay reached QA for the first time. The verifier passed after one
correction; QA then blocked on two one-line defects:

```
SIM102 Use a single `if` statement instead of nested `if` statements
  --> app/scoring.py:43:5
tests/test_route_toggles.py:119: AssertionError   (assert 8.0 < 8.0)
```

The loop spent **six fix rounds and 883k prompt tokens** on them and still
ended `reviewer_blocked`. The reason was in the report: the key-line extractor
dropped both. Ruff prints `RULE message` and puts the location on the *next*
line (`--> path:line:col`), and the extractor only kept lines matching
`error|fail|…`; the pytest line `path:line: AssertionError` was treated as
"path:line" plus a bare column, and `assert 8.0 < 8.0` matched nothing. The
coder received a 4k tail instead of two lines, and a free model does not find
the line in it.

`extract_error_lines` now pairs a ruff rule with its arrow, keeps
`path:line: message`, and treats `assert …` as a key line. That is the 007-T9
lesson again in a different format: the report is the loop.

### The step that never landed

The rerun with T11 made the failure even clearer. The plan's step 6 was

```
STEP 6: tests/test_route_toggles.py — Create the test file importing app.main …
```

The coder's final answer said "created test file" and **printed the whole file
in its answer** — but the run delta did not contain it. The file was never
written. The static checks were green (nothing to check), and the 019 verifier
spent two rounds and ~500k prompt tokens saying "file does not exist"; the
correction step also changed nothing, which the first T11 heuristic mislabelled
`unstable`.

Two fixes, both deterministic:

- **a step must land its file**: the target of `STEP n: <file> — …` has to appear
  in the run delta, or the attempt failed and is retried (then senior). This
  turns a 500k-token silent failure into a second attempt (`run.json.steps[].landed`);
- **stalled ≠ unstable**: a correction that changes nothing is a coder failure
  (`stalled`, `verifier_blocked`); `unstable` is reserved for a correction that
  *landed* and was still blocked on the same file in a different way.

### The verifier can re-litigate its own correction

The capability run (006, `coder=nemotron-3.5-super-vl:free`) got much further:
the self-check was green after one real type fix (113k tokens, 109 s), the test
file was complete, and the verifier still blocked — twice, with **opposite
instructions**:

| Round | Finding | Correction |
| --- | --- | --- |
| 1 | the two tests use identical route properties, so they only test one side of the toggle | use two fixtures, `lit: yes` vs `lit: no` |
| 2 | the tests now mock different properties per call, so they test different routes instead of the toggle | return **identical** properties for both calls |

Both readings can be defended, and the second directly undoes the first. The
coder did what it was told and the verifier re-blocked on the consequence. That
is not "the scenario is broken"; it is a verifier that judged the *test design*
instead of the AC, and changed its mind about the design. Two rules follow:

- do not prescribe how a test mocks, structures fixtures or names cases — require
  the behaviour the AC names (021 AC-11, prompt rule);
- a block after a **landed** correction on the same file is not authoritative:
  it becomes a warning (`verifier.overridden`) and QA's gates decide, because a
  subjective test-design preference must not make a run unconvergeable. A
  correction that changed nothing is `stalled` (coder failure) and still stops
  the run (021 AC-11).

This is the "too strict" question answered precisely: the **coder** was not too
strict (the strong coder completed the work); the **verifier** was too
prescriptive, and the harness now bounds that.

### Is the coder prompt too strict?

A fourth hypothesis came out of the 020 T8 replay: the step prompt's hard rules
("at most 5 tool calls", "never read the same file twice", `max_iter=6`) may
force a small coder to write from memory. The observed output is consistent with
it — a six-step plan for one file, a module with only the constants, and a test
with inverted expectations plus a duplicated method — but also with
over-decomposition and with model capability. T10 measures all three (loose
prompt, planner step count, stronger coder pin) instead of relaxing a guard that
exists to stop Qwen-9B wandering.

### The verifier judged the spec, not the task

The lightning bake-off run on `007-live-position-T2` made the remaining
verifier problem explicit. That task is "add `snap.ts` and `snap.test.ts`". The
verifier blocked it on:

1. using planar projection instead of spherical trigonometry (no AC asks for
   that precision), and
2. not being imported by a consumer — which is **T7/T8's** work in the same
   spec.

So the verifier was applying a senior-engineer quality bar to a unit task and
pulling a spec-level AC that a later task owns. That is the same class as
006-T3's test-design fight, and it explains why capable models still end
`verifier_blocked`.

Fix (T13): the verifier prefix now carries the task's own `tasks.md` line and a
scope rule — judge the brief and the referenced ACs; later tasks own their
wiring, UI, consumers and e2e; do not require an algorithm or precision the
brief does not state.

### Paid coder bake-off: the coder works, the local QA hangs

With `coder=zen/glm-5.3-flash` (paid, ~$0.15/M in) on `007-live-position-T2`:

| Run | What happened |
| --- | --- |
| 1 (2400 s cap) | 2 steps at 22:52–22:53, QA ran six gates **all green** at 22:55, a fix crew started at 22:57 and **hung on the Zen call** until the cap |
| 2 (900 s cap, 60 s LLM timeout) | 6 steps, QA ran the gates (`npm test` red), then the **local 9.7B QA model hung ~9 min** writing its verdict |

So the paid coder produces gate-green work quickly; the bottleneck moved to the **verdict/fix call**, and in run 2 specifically to the local QA model. That is a routing problem, not a coding problem: QA should not be a slow 9.7B model on a long report.

A third run with a fast cloud QA (`lightning`) and a 900 s cap removed the hang
(no 9-minute silence) but ran out of wall clock in the fix loop after `npm test`
came back red. A fourth run with a 1500 s cap got further — QA, a harness
fallback, two crews, one `task_failed`/`crew_failed` and a retry — and still hit
the cap. The loop was working, not stuck; the cap was too small for a two-step
task plus one repair round plus a retry.

That is the real measurement: **the loop has ~10 sequential model phases**
(planner, steps, self-check, verifier, QA, fix/retry), and at 30–90 s per call
that is 10–25 minutes before a failure is even decided. A paid coder removes the
capability problem; it does not remove the wall clock.

### Bake-off: the models are not the whole story

Two cases, `lightning` as coder and QA, 900 s per case:

| Case | Result |
| --- | --- |
| 007-live-position-T2 | `needs_human` / `verifier_blocked` (stalled), 1274 s, **826k tokens** |
| 010-e2e-playwright-T5 | timed out at 900 s |

A later validation run of 007 with the base-compatible formatter and the
senior-repair routing also **timed out at 2400 s**. The planner fix worked (the
run got past planning), but the loop did not finish; the worktree is now kept on
a timeout so the run record survives (it was removed before, which cost the
evidence for this attempt).

The 007 run is instructive. The self-check was red on Prettier, and the
formatter could not fix it because the **base commit predates the `lint:fix`
script** — `npm error Missing script: "lint:fix"` — which the harness did not
surface. The verifier then blocked on a legitimate finding (`distanceMeters`
returns degrees, though the name and the 30 m threshold imply meters), and the
correction step changed nothing (`stalled`). So the failure was three things at
once: a replay/tooling mismatch, a real semantic finding, and a repair crew that
could not act on it. Fixing the formatter to report its exit code is done; the
other two are the next phase's problem.

### The last red gate was the runner's own log

After the evidence fix, `004-weather-sun-T2` came back with **four gates green
and a QA pass**, and `scope: 1` as the only red gate. The scope violation was the
replay runner itself: it wrote `.swarm-replay.out/.err` **inside the worktree**,
which the harness correctly counted as out-of-scope changes. The logs now live in
a temp dir outside the tree. That is the difference between "the code is wrong"
and "the harness dirtied its own tree".

### QA can pass and the loop can still keep fixing

`004-weather-sun-T2` (one file) with the paid coder reached
`review_verdict=pass` and **four gates green at exit 0**, then started
`coder:fix1`, `senior:fix1/2` rounds until the wall budget: **731k prompt
tokens, $0.14** on a one-file task. The reason: the harness's gate map was not
green (stale/incomplete evidence) while QA's verdict was pass, and
`fixcause.classify` called that `other` — i.e. coder work. A coder round cannot
create a missing gate execution.

The loop now classifies "pass + no failing gate" as `evidence`: it re-runs the
evidence once and stops with a note, never a coder round. That is the difference
between a red-but-explained stop and a quarter-dollar loop.

## 022 measurement: the budget has to reach inside a crew

The first 022 suite run (three cases, paid coder + fast QA, `SWARM_TASK_WALL_BUDGET=900`, 1100 s runner cap) reproduced the old shape: **all three timed out, with no `run.json`**. The event logs showed why — the budget is checked *between* crews, but one crew's agent loop (`max_iter` × retries) can outlive it, so the runner killed a run that had no record.

Two fixes: every agent gets the remaining budget as `max_execution_time`
(`_apply_wall_cap`), and a killed replay derives `last_phase` from
`events.jsonl` and records `status=timeout` instead of an anonymous failure.

The single-case rerun (007, paid coder + fast QA, budget 900 s):

| Run | Result |
| --- | --- |
| before | timeout at 1100 s, **no `run.json`** |
| after | `needs_human` / **`wall_budget` at 917 s of 900 s**, 954 s total, 68,751 prompt tokens, **$0.0201**, 0 retries, `run.json` present |

So the budget is reachable and the record survives. The run also exposed two
attribution defects, both fixed: the sandbox clock jumped mid-run (a 954 s task
reported 3224 s / 6270 s phases), so events now carry a monotonic stamp that
phase durations prefer; and `crew_started` carried no role because CrewAI emits
it from its own thread, so the flow now registers the crew object with its role
and the listener resolves by object id.

**T6 verdict:** the wall budget and timing work; the AC-6 wall-clock target is
**not met** — 954 s (15.9 min) for a two-file case against a 10 min target, and
no case reached QA or green. The loop is still bounded by the paid model's
latency and the self-check/verifier phases, not by an unbounded hang.

A later verifier-bound rerun of 007 hung for **57 minutes with a 1300 s
timeout**. The cause was the runner's use of pipes: a leaked gate process kept
the pipe open after the flow exited, so `communicate` never returned even though
the flow was done. The replay child now writes to files instead of pipes, and
the timeout is a real bound again.

## 021 measurement: what the suite could and could not show

The outcome suite was attempted with the operator's `.env` routing plus a
capable coder pin (`nemotron-3.5-super-vl:free` for coder and QA). It did not
complete:

| Case | Result |
| --- | --- |
| 004-weather-sun-T2 | **timed out at 2400 s** (per-case timeout) |
| 005-saved-routes-T2 | `needs_human` / `verifier_blocked`, 747 s |
| 006-comfort-plus-T3 | **timed out at 2400 s** |
| 007 / 010 | not reached (the tool session died mid-suite) |

`swarm/bench/replay_baseline.json` records this as `complete: false`, with the
partial rows and the reason, rather than a claimed baseline.

The 021 behaviours themselves were exercised by the repeated 006 runs:

| Configuration | Result |
| --- | --- |
| local 9.7B coder | truncated test file, verifier blocked, ~180–404k tokens |
| strong coder | complete file; verifier blocked twice **contradictorily** (T11) |
| + T11/T12 | verifier **PASS** after one correction; step landing enforced |
| + key-line fix | QA reached; blocked on `SIM102` + one assertion after **6 rounds / 883k tokens / 1365 s** |

So the harness correctness fixes are validated — the loop now reaches QA and the
verifier no longer re-litigates — but the **efficiency targets cannot be
evaluated against a green baseline**: the loop does not converge on these cases
within a practical wall clock, and the 020 loop (the A/B's other side) times out
before finishing. The per-task cost (0.5–0.9M prompt tokens, 20–40 min) is the
blocking problem, and it is dominated by repair rounds on one-line defects, not
by prompt characters.

Decisions recorded: T4 (tests-first), T5 (AC-aware coder prompt) and T10
(loose prompt / planner step count) stay off/strict because no measured win
exists; `SWARM_REPLAY_TIMEOUT` and `--timeout` were added so an operator can run
the suite with a realistic bound; the next measurement needs a model bake-off
and a faster case set before it can serve as an A/B.

## Proposed 021 scope (`021-fix-loop`)

Measure first, then remove the mechanical class, then test the tests-first bet:

1. **Outcome suite + fix telemetry (R5, R9).** Before changing behaviour:
   5–8 frozen cases replayed on demand; `fix_cause` recorded per round; a
   `make swarm-report` view of cause distribution, 017/019 hit rate and
   `cached_prompt_tokens`.
2. **Deterministic repair before QA (R1, R2, R7).** Formatting never reaches a
   model; lint failures that `--fix` owns are repaired and re-checked; the
   pre-QA static set covers the frontend type check. No new trust surface: QA
   still runs the gates and owns green.
3. **Tests-first, as an A/B (R3, R4).** A red test step from the ACs, written by
   a separate test-author role and frozen; then the implementation steps. Run it
   on N cases against the current flow and keep it only if the fix rate drops
   without lowering the green rate. AC-aware coder prompts ride along as the
   cheap variant.
4. **Repair budget + checkpoint preservation (R6).** Stop at the measured knee,
   keep the best verified delta, and refuse a round whose evidence is stale.
5. **Contract pinning (R8)** if the A/B leaves room; otherwise record it for 022.

**Success (measured on the outcome suite, not the offline bench):**
fix-round rate 59% → **≤35%**, `coder:fix*` prompt tokens **−40%**, p50 wall
clock for fix tasks 615 s → **≤400 s**, and the green rate **not lower** than
the 020 baseline. A change that lowers green is reverted, not documented.

## Decision points

1. **Tests-first shape** — full phase (separate test-author crew, frozen tests)
   or an opt-in A/B (`SWARM_TESTS_FIRST=1`) that ships only if it wins?
   Recommendation: A/B, because ExecCritic shows a weak test author can make
   results *worse* than no test.
2. **Repair budget** — keep 3 fix rounds, or adopt the measured knee (4) with
   checkpoint preservation? Recommendation: 3 for local models, 4 only if the
   suite shows a gain.
3. **Scope** — does the outcome suite + telemetry belong in 021 (recommended:
   yes, it is how 022/023 will be judged) or a separate measurement spec?
4. **`fix_cause` ownership** — classify mechanically from the report (gates +
   key lines) or ask QA for one line? Recommendation: mechanical, with QA's
   reason as a fallback; a model-labelled cause is not evidence.

## Sources

- Repo: `swarm/runs/*/run.json` (86 runs), `swarm/report.py`, `swarm/style.py`,
  `swarm/flow.py` (`_autofix_style`, `_gates_or_evidence`), `specs/020-*`.
- Market: links inline above; the broader landscape is in
  `docs/research/dark-factory-market-2026.md`.
