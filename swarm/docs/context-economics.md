# Prompt and context economics (020)

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Prompt assembly (`swarm/prompts.py`, 020 T2)
One module builds every per-task prompt, in two parts:

```
description = stable_prefix(task, spec_dir, kind) + "\n\n" + volatile part
```

- `stable_prefix` is a pure function of the task and `specs/<spec>/`: task
  context (spec/task/AC ids, brief), the fixed rules for the role (scope,
  read-real-API, loop limits, the verifier's whole-scenario contract), and, for
  the verifier only, the referenced AC paragraphs and plan lines. The volatile
  tail is the step text, the round's report or the work summary, always last.
- `prompt_prefix(task, spec_dir, kind)` returns the provider-order prefix
  (role, goal, backstory, then the stable block) and its short SHA-256. The
  bench records the hash per case: if a change silently reassembles the head of
  the prompt, the hash moves instead of the character count drifting.
- Two steps (or two fix rounds) of the same task produce a byte-identical
  prefix. That is what makes provider prefix caching and Ollama KV reuse
  possible; the cache hints themselves land in 020 T3.
- Agent copy (role/goal/backstory) lives in `prompts.agent_copy(task, kind)`;
  `swarm/crew.py` only assembles CrewAI objects. `swarm/crew.py` re-exports the
  old names (`MAX_STEPS`, `SCOPE_RULE`, `FIX_RULES`, `parse_steps`, …) for the
  flow and the tests.
- Measured at T2: +5.7% task prompt chars over the T1 baseline (the brief is
  now part of every step's stable prefix), report chars unchanged. The win is
  cacheability and one coherent head per task, not raw characters; T4/T5/T6 do
  the cutting.

## Context compaction and gate-log spilling (`swarm/compaction.py`, 020 T4)
A fix round is the most expensive round, and it used to re-send everything:
the concatenation of every step output plus up to 4k chars of raw tail per
failing gate. Two rules keep it flat (`SWARM_CONTEXT_COMPACT=0` restores 019):

- **Step outputs become a digest.** Full outputs are written to
  `<run>/step_outputs/step-NNN.txt`; the prompt gets one line per step —
  index, files touched, the one-line outcome and the path to the rest. The
  checkpoint still holds the full outputs, so a resumed run loses nothing.
- **A long failing gate tail is spilled.** Above `SWARM_GATE_SPILL_CHARS`
  (default 2000) the tail goes to `<run>/gate_logs/<gate>.log`; the report keeps
  the extracted `file:line: message` key lines plus `full log: <path>`. The
  threshold is 2000, not the 4000 the spec first proposed, because the QA
  transcript already caps a tail at 4000 — a 4000 threshold could never fire.
- `shell_log.jsonl` now keeps up to `SWARM_GATE_TAIL_CHARS` (default 20000) per
  execution, and the report extracts key lines from that **whole** tail before
  truncating its prompt copy to 4k. That is what makes the 007-T9 lesson hold:
  the failure header is no longer cut away before the key lines are read.
- `run.json.compaction` records the mode, steps spilled, full/digest chars,
  chars saved, the threshold and every gate log path.

Measured at T4: task prompt **427,725 chars (−7.4%)**, report **5,768 chars
(−86%)** over the same 12 cases.

## Gate selection (`swarm/gates.py`, 020 T5)
A frontend-only delta does not need `pytest`; a Python delta does not need
`svelte-check`. The inner loop now runs only what the delta can affect:

```
app/**=pytest -q;ruff check .;mypy app tests
tests/**=pytest -q;ruff check .;mypy app tests
contracts/**=pytest -q
frontend/**=npm --prefix frontend run check;npm --prefix frontend run lint;npm --prefix frontend test -- --run
```

- `SWARM_GATE_MAP` overrides the map (newline separated `glob=cmd;cmd`).
  An **unmapped** path selects every command: fail-open is the only safe
  direction for a new area.
- Selection is inner-loop only. The first QA round runs the full suite, and a
  fix round that is green on the selected subset must pass a final
  `qa:full-suite` round before the run can be green; a failure there re-enters
  the fix loop with the full-suite report.
- QA remains the only gate executor. `flow.gate_scope()` narrows
  `SWARM_GATE_COMMANDS` for the duration of a round, so the QA prompt's gate
  hint and the evidence collector can never disagree.
- `run.json.gate_selection` records `mode`, `selected`, `skipped`, the last
  rounds and `affected_gates`/`full_gates`; the `gate` listener marks a run
  `needs_human` if the last round is still `affected`.
- `SWARM_GATE_SELECT=0` disables selection (always full).

Measured at T5: **36 gate runs/round vs 60 (−40%)** on the frozen corpus.

## Reports and search (020 T6)
- `report_text` renders the failing gates first with their `file:line: message`
  key lines. The raw tail is a fallback, shown only when extraction found
  nothing (`output:`); when a tail was spilled the report carries
  `full log: gate_logs/<gate>.log` instead. A failure is never sent twice.
- `run.json.qa_report` carries `version: 2` and `report_chars`, so the size the
  coder actually received is auditable next to the bench number.
- `Repo Search` (`SearchTool`) is registered for coder and senior crews only:
  a Python regex, optional repo-relative path, `path:line: text`, max 40 hits,
  no shell, no writes, secret paths and vendor/build/run directories skipped.
  Its description is one line on purpose — it is in every step prompt.
- The coder read cap is `SWARM_CODER_READ_CHARS` (default 3000). The verifier's
  `FullFileReadTool` ignores it and keeps `SWARM_VERIFY_READ_CHARS`; QA gets
  neither search nor a widened read.

Measured at T6: task prompt **431,359 chars (−6.6%)**, report **5,768 (−86%)**.
The prompt is slightly above T5 because the search tool's description is part
of every coder prompt; the tool exists to stop the 014-T1 class of loop, which
cost 229 calls and a `no_progress` stop.

## Prompt caching (`SWARM_PROMPT_CACHE`, 020 T3)
Prefix caching is a provider feature; what the harness can do is (a) keep the
prefix byte-identical (T2) and (b) send a hint where a provider accepts one.

| Route | Cache | What we do |
| --- | --- | --- |
| `ollama/*` | automatic KV reuse for an identical prefix | nothing to send |
| `openrouter/*` | automatic for supporting models (`prompt_tokens_details.cached_tokens`) | nothing to send |
| `zen/*` | none | nothing |
| direct `anthropic/*` | ephemeral `cache_control` | hint sent; on rejection the plain LLM is built |

`llms.cache_support(model)` decides, `llms.cache_modes()` records the result in
`run.json.cache` (with `cached_prompt_tokens`), and `SWARM_PROMPT_CACHE=0` turns
every hint off. The default routing (Ollama + OpenRouter) caches automatically,
so the measured signal is `usage.cached_prompt_tokens`, not a request field.

## 020 knobs
Every behaviour added in 020 has an off switch that restores the 019 behaviour;
`make swarm-test` covers both paths.

| Knob | Default | Effect |
| --- | --- | --- |
| `SWARM_PROMPT_CACHE` | `1` | provider cache hints (T3); `0` = plain LLM calls |
| `SWARM_CONTEXT_COMPACT` | `1` | step digests + gate-log spilling (T4); `0` = full concatenation, tails in the report |
| `SWARM_GATE_SPILL_CHARS` | `2000` | a failing tail longer than this goes to `gate_logs/` |
| `SWARM_GATE_TAIL_CHARS` | `20000` | how much of one execution `shell_log.jsonl` keeps (the source for key lines) |
| `SWARM_GATE_SELECT` | `1` | inner-loop gate selection (T5); `0` = always the full suite |
| `SWARM_GATE_MAP` | repo defaults | newline-separated `glob=cmd;cmd`; an unmapped path runs everything |
| `SWARM_CODER_READ_CHARS` | `3000` | coder read cap (T6); the verifier keeps `SWARM_VERIFY_READ_CHARS` |
| `SWARM_BENCH_CASES` | 12 default cases | `spec/Tn` list for `make swarm-bench-build` |
| `SWARM_BENCH_MODELS` | unset | pinned models for `make swarm-bench-live` |
