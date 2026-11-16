# 033 Planner-Coder Chain — Spec

Control-plane spec (add `033-planner-coder-chain` to `HARNESS_SPECS`): the queue
never runs it.

## Problem

The planner-coder chain wastes the SDD convention and misassigns fidelity.

1. **`plan.md` is ignored.** Every spec has a `plan.md` ("approach, steps,
   risks") — that is the point of spec-driven development. The planner never
   reads it: its prompt carries the task brief and the ACs and asks the model to
   re-derive the approach. `plan_source_hash` uses `plan.md` only to invalidate
   the cache. The planner re-does work the spec already did, every task.
2. **The micro-steps are code strings, not intent.** `PLAN_RULES` requires each
   step to name the module, the import path and the functions it calls — solving
   the task at API fidelity before the coder runs. The coder is handed that
   string verbatim; a hallucinated name propagates (007-T9's duplicate
   `walkMode` module). The coder is *also* told to read the real module — the
   detail is redundant and dangerous.

`docs/research/planner-coder-2026.md` records this and the market's answer:
the plan is intent + acceptance; the implementer owns the how.

## Goal

Feed the planner the human `plan.md`, have it decompose into **logical, intent-
level steps** (one acceptance criterion each, files optional, API names
forbidden), and let the coder own the implementation. Record which plan source a
run used, and keep the change reversible and measured.

## Scope

- `swarm/prompts.py`:
  - `plan_prompt` includes the task's `plan.md` lines (the same bounded
    `plan_lines` helper the verifier already uses);
  - `PLAN_RULES` rewritten: "decompose the plan into logical steps, one
    acceptance criterion each; name only the files a step may touch; never
    invent a function, import path or field name — the coder reads the real
    module";
  - `step_prompt` reworded: the step is an intent, the coder chooses the
    implementation.
- `swarm/flow.py`:
  - the planner reads `plan.md` through `plan_prompt`; `plan_text` in the cache
    is still the planner's STEP list (cache semantics unchanged);
  - `run.json.plan_src` ∈ `{"plan.md", "derived", "cached"}` and
    `run.json.plan_steps` (count) are recorded;
  - `SWARM_PLAN_USE_MD=0` restores today's derive-from-ACs prompt; `--replan`
    still forces a fresh derive and clears the cache.
- `docs/research/planner-coder-2026.md` (the evidence), and the changelog.

## Non-goals

- Making the planner approve or edit `plan.md` (the swarm does not edit specs).
- Changing the coder's scope, the verifier, or the fix loop.
- Splitting one step into multiple files (the "one cohesive change per step"
  wording stays; only the instruction fidelity changes).

## Acceptance criteria

- **AC-1 — The planner reads the plan.** With `SWARM_PLAN_USE_MD=1` (default),
  the planner's prompt contains the task's `plan.md` lines and the ACs; with
  `=0` it contains only the ACs (today's prompt). A prompt-level test asserts
  both.
- **AC-2 — Steps are intent, not code.** The new `PLAN_RULES` forbids inventing
  API names and asks for one acceptance criterion per step; the `step_prompt`
  names the step as an intent. Tests: the prompt text contains the forbidding
  sentence and not the old "name the import path and the functions it calls".
- **AC-3 — The coder still owns the how.** `STEP_RULES` keeps "read the real
  module, use its real API" and the step text no longer claims to contain the
  code to write. Test: the step prompt no longer includes the step verbatim as
  "execute micro-step … <code>", but as "execute logical step … <intent>".
- **AC-4 — The source is recorded.** `run.json.plan_src` is `cached` when the
  plan came from the cache, `plan.md` when the planner used the plan, `derived`
  otherwise; `plan_steps` is the count. A save_run-level test covers each.
- **AC-5 — Reversible and measured.** `SWARM_PLAN_USE_MD=0` is honoured
  end-to-end (a prompt-level test is enough); the change is A/B'd against the
  replay suite and `make swarm-bench` so the green rate and prompt chars are both
  recorded (`replay_baseline.json` / `changelog.md`), and the acceptance is
  "green rate not lower", never "fewer tokens".
- **AC-6 — Tests and docs.** `make swarm-test` covers the prompt changes and the
  `plan_src` recording; `033-planner-coder-chain` is in `HARNESS_SPECS`;
  `docs/research/planner-coder-2026.md` and the changelog record it.

## Evidence

`swarm/prompts.py` (`PLAN_RULES`, `task_block(plan=…)`, `step_prompt`),
`swarm/flow.py` (`plan_source_hash`, `plan_cache_path`, the `_kickoff` plan
path), `swarm/verify.py` (`plan_lines`), the 007-T9 duplicate-module incident,
and `docs/research/planner-coder-2026.md`.

## Success definition

A task is planned as a small number of logical steps derived from the human
plan, the coder invents the code from the real modules (not from planner-written
strings), and the run says where its plan came from — with the replay suite
proving the loop still converges at least as often.
