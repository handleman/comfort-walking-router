# 020 Harness Efficiency — Spec

Control-plane spec (added to `HARNESS_SPECS`): the queue never implements it.

## Problem

The harness works, but it is not efficient, and nothing measures whether a
change makes it better. The baseline from `swarm/runs/` (2026-11-12):

| metric | value |
| --- | --- |
| runs / green | 86 / 54 (**63%**) |
| cost per green task | mean **$0.039**, median **$0.021** |
| fix-round rate (green runs) | **59%** |
| wall clock per green task | p50 **426 s**, p90 **1663 s** |
| biggest token consumers | QA **4.82M** prompt tokens, `coder:fix1` **3.22M**, `fix2` **2.06M** |
| stops | `needs_human` 15, `crew_error` 8, `budget_exhausted` 8, others 7 |

Four specific inefficiencies are visible in the code and in the run history:

1. **Every round re-sends a large prompt.** Each crew is built fresh with the
   full role/backstory/scope/brief/plan text; nothing keeps a byte-stable
   prefix, so provider prefix caching (and local Ollama prefill reuse) cannot
   help even where it is free. `run.json` already records
   `usage.cached_prompt_tokens`, but almost nothing is cached.
2. **Every fix round re-runs the whole gate suite.** A frontend-only delta
   still runs `pytest`, `ruff`, `mypy`, `npm check`, `npm lint` and `npm test`.
   The full suite is the right *final* gate; it is the wrong *inner-loop* gate.
3. **Raw output is kept in context.** `work_summary` joins the full text of
   every micro-step, and the QA report embeds up to 3k chars of tail per failing
   gate. Long runs pay for the same text many times, and the coder still
   sometimes misses the one line that matters.
4. **There is no replay set.** The 86 historical runs are evidence about the
   past, not a baseline for a change: different tasks, models and repo states.
   A prompt or gate change cannot be A/B'd, so an "optimization" is anecdote.

The market has already converged on the fixes: prefix-stable prompts plus
provider prompt caching, context compaction with tool-result spilling, and
test-impact selection in CI. The investigation
(`docs/research/dark-factory-market-2026.md`) maps them to this harness.

## Goal

Cut tokens and wall clock per green task **without lowering the green rate**,
and make every later harness change measurable against a frozen replay set.

The phase is deliberately a harness change, not a framework migration: stay on
the CrewAI Flow (decision 2026-11-12). A durable, event-sourced orchestrator
layer is a future option, not part of 020.

## Scope

- A frozen benchmark corpus from historical runs plus an opt-in live replay.
- Prefix-stable prompt assembly and provider cache hints where supported.
- Context compaction: step-output digest, gate-log spilling, bounded reports.
- Test-impact gate selection in the fix loop; full suite before green.
- A guarded search tool and an adaptive coder read cap (3k stays the default).
- Measurement: before/after table, success thresholds, knobs and docs.

## Non-goals

- Parallel micro-steps or concurrent task workers (that is 021).
- Risk classes, earned auto-merge, post-PR loop (that is 022).
- Migrating off CrewAI or introducing an event-sourced orchestrator now.
- Any deploy-to-production loop.

## Acceptance criteria

- **AC-1 — Frozen replay corpus.** `swarm/bench/` builds a deterministic corpus
  from selected historical green runs. A case records the task brief, the AC
  refs, the plan, the delta file contents at the green commit, the recorded
  gate/report sizes, and the base commit (`green_commit^`). The manifest pins
  run id, commit, and a content hash per file. The corpus can be rendered with
  no model call and no repository write; `make swarm-bench` reports per-case
  prompt chars, estimated tokens, report chars and a stable digest. A baseline
  snapshot (`swarm/bench/baseline.json`) is committed **before** any prompt or
  gate change.

- **AC-2 — Prefix-stable prompts.** Prompt text is assembled by one module
  (`swarm/prompts.py`), stable content first (role, goal, backstory, scope,
  fixed rules, brief, ACs, plan) and variable content last (step, round,
  report). A test asserts that two steps/rounds of the same task produce a
  byte-identical stable prefix. `prompt_prefix(task)` returns that prefix and
  its hash; the bench records the hash per case. Provider cache hints are
  attached where the provider supports them; `SWARM_PROMPT_CACHE=0` disables
  them. The existing `usage.cached_prompt_tokens` remains the measured signal.

- **AC-3 — Context compaction and tool-result spilling.** `work_summary` is a
  bounded digest (step index, action, files touched, one-line outcome), not the
  concatenation of full step outputs; the full outputs are written to
  `<run_dir>/step_outputs/` and referenced by path. A failing gate tail larger
  than `SWARM_GATE_SPILL_CHARS` (default 4000) is written to
  `<run_dir>/gate_logs/<gate>.log`; the report carries key lines and the log
  path. `run.json.compaction` records what was spilled and the resulting chars.
  `SWARM_CONTEXT_COMPACT=0` restores the old behaviour.

- **AC-4 — Test-impact gate selection.** `swarm/gates.py` maps changed paths to
  the gates that can be affected (`SWARM_GATE_MAP`, with a safe default: an
  unmapped path selects every gate). The fix loop runs only the selected gates;
  before a run can be green, the **full** `SWARM_GATE_COMMANDS` suite runs once
  at the final delta. `run.json.gates` records `mode` (`affected`/`full`),
  `selected`, `skipped` and the full-suite result. QA remains the only gate
  executor: selection changes *which* gates QA is asked to run, never who
  records the evidence. `SWARM_GATE_SELECT=0` disables selection.

- **AC-5 — Structured reports and coder search.** The coder receives failure
  key lines plus a locator, not a raw tail twice; `report_chars` and
  `report_version` are recorded. Coders get a guarded `SearchTool`
  (`file:line: text`, repo-relative, secret-guarded, bounded results) so a
  defect can be found without re-reading the same range; the coder read cap
  becomes `SWARM_CODER_READ_CHARS` (default remains 3000).

- **AC-6 — Live replay (opt-in).** `make swarm-bench-live CASE=<id>` creates a
  disposable worktree at the case base commit, copies the current harness into
  it, runs the case end to end with pinned models and a scratch runs directory,
  records the same metrics as the offline bench, and refuses to run on the
  primary worktree or with a dirty tree. The worktree and its runs are removed
  on success; failures leave the path in the report.

- **AC-7 — Measured result.** The change ships with a before/after table in
  `docs/research/dark-factory-market-2026.md` (or a linked results file) and a
  `changelog.md` entry. Targets: per-case prompt chars **−30%**, report chars
  **−40%**, gates per inner-loop round **−40%** for a single-area delta, and
  a live replay of at least one case with the **same green status** and either
  **−25% wall clock** or **−30% tokens**. If a target is missed, the measured
  number and the reason are recorded; a change that worsens the green rate is
  reverted, not documented as a win.

- **AC-8 — Knobs and defaults.** Every new behaviour has a documented knob
  (`.env.example` + `swarm/README.md`) with a safe default:
  `SWARM_PROMPT_CACHE`, `SWARM_CONTEXT_COMPACT`, `SWARM_GATE_SPILL_CHARS`,
  `SWARM_GATE_SELECT`, `SWARM_GATE_MAP`, `SWARM_CODER_READ_CHARS`,
  `SWARM_BENCH_CASES`, `SWARM_BENCH_MODELS`. Disabling every knob restores the
  019 behaviour; `make swarm-test` covers both paths.

- **AC-9 — Provenance for future replays.** Every run records `base_sha` and
  `head_sha` (or `null` when git is unavailable) and the plan hash in
  `run.json`, so a future corpus can be built from the run itself instead of
  re-deriving it from `git log --grep`. The bench builder prefers the recorded
  values and falls back to the commit trailer.

## Evidence

- Baseline: `swarm/runs/` (86 runs, 54 green) and `make swarm-report`.
- Market patterns: `docs/research/dark-factory-market-2026.md` §"Growth
  opportunities" (E1–E5, L1).
- Historical defects that motivate the read/report work: 014-T1 (repeated
  truncated reads → `no_progress`), 007-T9 (failure text lost to the report
  cap).

## Success definition

`make swarm-bench` is the same or better than `baseline.json` on green
proxies, and the AC-7 targets are met or honestly reported. The phase does not
claim a speed win from concurrency; it removes work the loop did not need.
