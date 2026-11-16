# 020 Harness Efficiency — Tasks

Control-plane spec (`HARNESS_SPECS`): the queue never runs these.

- [x] T1 (AC-1, AC-9): add `swarm/bench/` — build a frozen corpus from green runs (brief, ACs, plan, delta file contents at the green commit, base `green_commit^`), reject a case whose commit does not touch a file the brief names, commit `baseline.json`, and make `make swarm-bench` render per-case prompt/report chars, estimated tokens and a stable digest with no model call and no repo write.
  Evidence: `swarm/bench/corpus.py`, `swarm/bench/score.py`, `swarm/bench/baseline.json`, `swarm/tests/test_bench.py`.
- [x] T2 (AC-2): add `swarm/prompts.py` — one pure assembly point with a byte-stable `stable_prefix(task, spec_dir, kind)` (role rules, scope, task context/brief, and the ACs/plan for the verifier) and volatile `step`/`fix`/`qa`/`verify` prompts; `crew.py` builds descriptions and agent copy from it; `prompt_prefix` returns the prefix hash and the bench records it per case. A test asserts the prefix is identical across steps of one task and changes with the brief.
  Evidence: `swarm/prompts.py`, `swarm/crew.py`, `swarm/tests/test_prompts.py`, `swarm/bench/score.py` (prefix hash).
- [x] T3 (AC-2, AC-8): add provider cache hints in `swarm/llms.py` behind `SWARM_PROMPT_CACHE` (default on), with a plain-LLM fallback when a provider rejects the field; record the per-model decision in `run.json.cache` and keep `usage.cached_prompt_tokens` as the measured signal.
  Evidence: `swarm/llms.py`, `swarm/flow.py`, `swarm/tests/test_cache.py`.
- [x] T4 (AC-3): compact the fix-round context — `work_summary` becomes a bounded step digest, full step outputs go to `<run_dir>/step_outputs/`, failing gate tails over `SWARM_GATE_SPILL_CHARS` (2000; 4000 could never fire over a 4k transcript) go to `<run_dir>/gate_logs/`, and `run.json.compaction` records the spill. `shell_log.jsonl` keeps `SWARM_GATE_TAIL_CHARS` (20000) per execution and key lines are extracted from the whole tail. `SWARM_CONTEXT_COMPACT=0` restores 019 behaviour.
  Evidence: `swarm/compaction.py`, `swarm/flow.py`, `swarm/evidence.py`, `swarm/tests/test_compaction.py`.
- [x] T5 (AC-4): add `swarm/gates.py` — map changed paths to affected gate commands (`SWARM_GATE_MAP`, fail-open on an unmapped path), run only those in the fix loop, run the full suite once before green, and record `run.json.gate_selection` (`mode/selected/skipped` + the gate results). A green subset is refused as green until the full suite confirms the final delta. `SWARM_GATE_SELECT=0` disables selection.
  Evidence: `swarm/gates.py`, `swarm/flow.py`, `swarm/bench/score.py` (gates/round), `swarm/tests/test_gates.py`.
- [x] T6 (AC-5, AC-8): ship structured reports and a guarded `SearchTool` — key lines plus a spilled-log locator, never the same tail twice (the raw body is only rendered when extraction found nothing); `report_version=2` and `report_chars` recorded; coders can search `path:line: text` without re-reading a range; `SWARM_CODER_READ_CHARS` overrides the 3000-char cap for coders only (the verifier keeps its own).
  Evidence: `swarm/evidence.py`, `swarm/tools_guarded.py`, `swarm/flow.py`, `swarm/tests/test_search.py`.
- [x] T7 (AC-6): add `make swarm-bench-live CASE=<id>` — refuse a dirty/primary tree, create a disposable worktree at the case base commit, copy the current harness in, run the case with pinned models (`SWARM_BENCH_MODELS`) and a scratch runs dir, report status/tokens/wall clock/fix rounds, and remove the worktree on success (kept and printed on failure). No commit/push; opt-in only.
  Evidence: `swarm/bench/live.py`, `swarm/bench/__main__.py`, `Makefile`, `swarm/tests/test_bench_live.py`.
- [x] T8 (AC-7): measure and report — the offline table is filled from `baseline.json` vs the new bench (prompt −6.6%, report −86.1%, gates −40%); `make swarm-bench-live CASE=004-weather-sun-T2` was run and ended `needs_human`/`verifier_blocked` (1050 s, 309k tokens, 0 QA rounds; the self-check and verifier could not repair a missing function and a duplicated inverted test). The green-status target is recorded as **missed** with its numbers and reason; the off-switch A/B is **not applicable** because the run never reached QA. Nothing was reverted: no 020 change lowered a green run — they did not participate in this one.
  Evidence: `docs/research/dark-factory-market-2026.md` (results + live replay), `changelog.md`.
- [x] T9 (AC-8, AC-9): close the loop — add `020-harness-efficiency` to `HARNESS_SPECS`, record `base_sha`/`head_sha`/`plan_hash` in `run.json` for future replays (the corpus prefers the recorded base), `SWARM_BENCH_CASES` selects the corpus, document every knob in `.env.example` and `swarm/README.md`, update `AGENTS.md`/`docs/roadmap.md`, and run `make swarm-test`, `ruff check .`, `mypy app tests`.
  Evidence: `swarm/flow.py` (`HARNESS_SPECS`, `save_run`), `swarm/bench/corpus.py`, `.env.example`, `swarm/README.md`, `AGENTS.md`, `docs/roadmap.md`.

## Decisions (2026-11-12)

- **Next spec scope:** efficiency first (this spec). Parallelism is 021;
  earned autonomy is 022.
- **Autonomy envelope:** earned autonomy by risk — class 0/1 (docs, tests,
  mechanical) may auto-merge after gates + verifier; class 2/3 (logic, auth,
  infra, the harness) stay human. Expand only on measured agreement/escape
  rates. Not implemented in 020.
- **Architecture stance:** stay on the CrewAI Flow and harden it. A durable,
  event-sourced orchestrator layer (append-only journal, replay, resumable
  nodes) is recorded as a future option, not a 020 deliverable.
- **Measurement:** the frozen replay set is part of 020 (T1/T7/T8).

## Phase 020 evidence

The baseline is 86 runs / 54 green (63%), $0.021 median per green task, a 59%
fix-round rate, and p50/p90 wall clock of 426 s / 1663 s. QA alone consumed
4.82M prompt tokens and the first fix round 3.22M. The harness re-sends full
prompts, re-runs every gate in every round and keeps raw output in context —
the three patterns the market has already solved with prefix caching,
compaction and test-impact selection. See
`docs/research/dark-factory-market-2026.md`.
