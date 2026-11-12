# 020 Harness Efficiency — Plan

Status: in progress (T1 corpus + baseline committed; T2 prompt assembly done). References `specs/020-harness-efficiency/spec.md` AC-1–AC-9 and
`docs/research/dark-factory-market-2026.md`.

## Approach

Measure first, then remove work the loop does not need, then measure again.
Every change is a knob with the 019 behaviour as the off switch.

```
T1  corpus + baseline snapshot + offline bench
        │
        ├─ T2  prompts module (stable prefix) ── T3 cache hints
        │
        ├─ T4  compaction + gate-log spilling
        ├─ T5  test-impact gate selection ── full suite before green
        └─ T6  structured report + coder search
                 │
                 └─ T7  live replay (worktree at green_commit^)
                          │
                          └─ T8  before/after table, thresholds
                                   └─ T9  docs, knobs, HARNESS_SPECS, gates
```

T1 must land before any prompt/report edit, because its baseline is the "before"
side of the comparison. T2–T6 are independent after T1; T7 depends on T1 and
the harness copy being importable from the worktree. T8/T9 close the loop.

## T1 — the benchmark corpus

`swarm/bench/` is a small package with four parts:

- `corpus.py`: select cases from `swarm/runs/*/run.json` where `status=green`,
  a commit with `Swarm-Task: <spec>/<task>` exists, and `git show --stat` names
  at least one file the brief names (the 007-T9 lesson: a trailer is not proof).
  For each case record `run`, `spec`, `task`, `brief`, `ac_refs`, `plan`,
  `changed`, `base_sha = green_commit^`, `green_sha`, and per-file content at
  `green_sha` (bounded by a per-case char budget; oversized files are recorded
  by name and size). Write `swarm/bench/corpus/<case>/manifest.json` plus a
  `files/` tree, or one JSON per case if the corpus stays small.
- `render.py`: rebuild the prompts and reports from a case with no model call.
  It imports `swarm/prompts.py` (T2) once it exists; before T2 it wraps the
  current `build_*_crew` argument strings.
- `score.py`: per-case prompt chars, estimated tokens (`chars/4`), report chars,
  prefix hash, gate commands, and a stable digest; aggregate green proxies from
  the selected runs (cost, fix rate, p50/p90).
- `baseline.json`: the committed snapshot. `make swarm-bench` prints a table and
  exits non-zero if a case is missing or the digest changed unexpectedly
  (`--update-baseline` is an explicit operator action).

The corpus is **read-only**: no model calls, no repo writes, no git mutation.

## T2 — one prompt module

Move the prompt text out of `build_*_crew` into `swarm/prompts.py`:

```python
def stable_prefix(task, spec_dir) -> str        # role/scope/rules/brief/ACs/plan
def step_prompt(task, step, index, total) -> str
def fix_prompt(task, report_block, qa_note) -> str
def qa_prompt(task, work_summary) -> str
def verify_prompt(task, context_text) -> str
```

`stable_prefix` is a pure function of the task and spec files; it is the part a
provider can cache. The volatile part is appended last. `crew.py` keeps building
CrewAI `Agent`/`Task` objects, but the description is `prompts.step_prompt(...)`
etc. A test asserts `stable_prefix` is byte-identical for step 1 and step 7 of
the same task, and differs when the brief changes (no stale cache across tasks).

Do **not** move the `FullFileReadTool`/`ShellTool` tool descriptions; they are
part of the provider's tool block and already stable.

## T3 — cache hints

`llms._build` gains an optional `cache_hints` path:

- Anthropic-compatible models: attach `cache_control` to the stable prefix via
  `extra_body` where the gateway accepts it.
- Ollama and OpenAI-compatible prefix caching: automatic; nothing to send, but
  the prompt must stay prefix-stable (T2).
- `zen/` gateway: no cache hint; keep the flag off.

The flag is `SWARM_PROMPT_CACHE` (default `1`). A provider that rejects the
extra field must not fail the run: `_build` catches the construction error and
falls back to the plain LLM. `run.json.usage.cached_prompt_tokens` is already
recorded; the bench compares it where the provider reports it.

## T4 — compaction and spilling

In `flow.run_crew`:

- Replace `work_summary = "\n".join(step_outs)` with
  `summary = compact_step_outputs(step_outs, run_dir)`:
  - write each full output to `<run_dir>/step_outputs/step-<n>.txt`;
  - return `--- step n/N --- <first line> [<files>] <outcome line> (full: step_outputs/step-n.txt)`.
- In `evidence.qa_report`/`report_text`, when a failing tail exceeds
  `SWARM_GATE_SPILL_CHARS`, write it to `<run_dir>/gate_logs/<slug>.log` and
  replace the body with key lines + `full log: <path>`.
- `run.json.compaction = {"steps_spilled": n, "gate_logs": [...], "chars_saved": n}`.
- `SWARM_CONTEXT_COMPACT=0` keeps the old `"\n".join(step_outs)` and in-report
  tails.

The digest must preserve the information a fix round needs: which step failed,
which file it touched, and the one-line result. It is not a prose summary; it
is generated from the step text and the first/last non-empty output lines.

## T5 — gate selection

`swarm/gates.py`:

```python
def select_gates(changed: list[str], commands: list[str], mapping: str) -> list[str]
def gate_map(env) -> list[tuple[str, list[str]]]   # SWARM_GATE_MAP
```

Mapping syntax: `path-glob=command1;command2`, separated by newlines. Defaults
for this repo (overridable):

```
app/**=pytest -q;ruff check .;mypy app tests
tests/**=pytest -q;ruff check .;mypy app tests
frontend/**=npm --prefix frontend run check;npm --prefix frontend run lint;npm --prefix frontend test -- --run
contracts/**=pytest -q
```

An unmapped path selects every command (fail-open). The flow runs the selected
subset in the fix loop; `_gates_or_evidence` accepts a `commands` argument.
Before `gate` can return green, the flow runs the full `gate_commands()` once at
the final delta and records it (`mode="full"`). QA still executes the gates;
the harness fallback covers a skipped one exactly as today.

Risk: a selected-gate round can pass while an unselected gate would fail. That
is why the full suite runs before green and why the full-suite result — not the
selected one — is the merge evidence.

## T6 — report + search

- `report_text` keeps key lines first; the raw tail is either the spilled
  locator or a short excerpt, never both. Add `report_chars` and
  `report_version=2`.
- `SearchTool` in `tools_guarded.py`: repo-relative directory + regex, walks
  tracked/source files (same pruning as `verify.connections`), returns
  `path:line: text` up to a cap, secret paths excluded, no shell. Registered for
  coder/senior/fix crews only (not QA, not the verifier).
- `TrimmedFileReadTool.max_observation` reads `SWARM_CODER_READ_CHARS`
  (default 3000; the verifier keeps `FullFileReadTool`).

## T7 — live replay

`swarm/bench/live.py`:

1. Refuse if `git status --porcelain` is non-empty or the case has no `base_sha`.
2. `git worktree add --detach <tmp> <base_sha>`.
3. Copy the current harness into `<tmp>/swarm/` (exclude `.venv`, `runs`,
   `__pycache__`, `bench/corpus`), symlink or reuse `swarm/.venv`.
4. Run `python -m swarm.flow --spec <spec> --task <task>` with
   `PYTHONPATH=<tmp>`, a scratch `swarm/runs`, pinned models from
   `SWARM_BENCH_MODELS`, and `SWARM_BENCH=1` (no commit/push, no TUI).
5. Read the run's `run.json` for status, tokens, wall clock, fix rounds; print
   the same metrics as the offline bench; remove the worktree on success.

The case task must be open at `base_sha` (it is, because the base is the green
commit's parent). If the green commit touched files the brief does not name,
the case is rejected at corpus build time.

## T8 — measurement

- Snapshot `baseline.json` at T1.
- After T2–T6, run `make swarm-bench` and write a table:
  `case, prompt chars before/after, report chars before/after, gates/round
  before/after`.
- Run `make swarm-bench-live CASE=<one small case>` for the live number.
- If the green rate on the replay drops, revert the offending change; do not
  trade correctness for tokens.

## T9 — docs and controls

- `HARNESS_SPECS += ("020-harness-efficiency",)`.
- `swarm/README.md`: the bench, the knobs, the prompt/compaction/gate-selection
  rules, and how to read `run.json.compaction`/`gates.mode`.
- `AGENTS.md`: one line in the state section and one harness lesson (measure
  with the replay set; a token win that lowers green is not a win).
- `docs/roadmap.md`: mark 020 implemented; record 021 (parallel) and 022
  (earned autonomy by risk) as next, with the decision date.
- `changelog.md`: the measured result.
- `make swarm-test`, `ruff check .`, `mypy app tests`.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Compaction drops the line a fix round needs | Keep key lines + locator; a test replays a 007-T9-style failure and asserts the failing `file:line` survives |
| Gate selection lets a real failure through | Full suite before green is mandatory; selection is inner-loop only; fail-open on unmapped paths |
| Prefix caching hints break a provider | Construction falls back to the plain LLM; `SWARM_PROMPT_CACHE=0` |
| Bench marks a cheaper run that is not green | Green proxies are part of the score; AC-7 requires the same green status on live replay |
| Worktree copy drifts from the real harness | Copy the `swarm/` package at run time; pin the base by SHA; refuse a dirty tree |
| A "benchmark" becomes a second product | Offline corpus is read-only and small (≤12 cases); live replay is opt-in and one case at a time |
