# Planner fidelity vs. coder freedom

Date: 2026-11-16. Input for `specs/033-planner-coder-chain/`. Complements
`docs/research/dark-factory-market-2026.md` (the dark-factory framing) and
`docs/research/fix-loop-2026.md` (the fix loop).

## The problem, from our own code

Two facts are visible in the harness today, not guessed:

1. **The planner never reads `plan.md`.** `swarm/prompts.py::task_block` takes a
   `plan` flag that is `True` only for the scenario verifier. The planner's
   prompt (`stable_prefix(..., kind="plan")` + `PLAN_RULES`) gets the task brief
   and the referenced AC paragraphs, and is told to *re-derive* the plan. The
   human-authored `specs/NNN-name/plan.md` — the SDD convention's actual
   "approach, steps, risks" — is hashed into `plan_source_hash` (so an edit
   invalidates the cached plan) but never read as a plan. The planner re-does
   work the spec already did.

2. **The micro-steps are code, not intent.** `PLAN_RULES` requires each step to
   "name the module under test, the import path to use and the functions it
   calls", and to "never plan a call to a function you have not seen" — the
   planner is asked to *solve* the task, at API fidelity, before the coder runs.
   The coder then receives that string verbatim. If the planner hallucinates a
   name, the coder inherits it; 007-T9's duplicate `walkMode` module came from a
   plan naming a module that did not exist. At the same time `STEP_RULES` tells
   the coder to read the real module and use its real API — so the planner's
   API-level detail is both redundant (the coder reads anyway) and a source of
   error (it can be wrong and is taken as instruction).

Net: the planner spends tokens to re-derive an approach we already have, at the
wrong fidelity, and passes strings to a coder that is separately instructed to
re-read the truth.

## What the market does

- **StrongDM Attractor** ("the first dark factory", NLSpecs in) treats the spec
  as the source of truth and the pipeline as the *how*: the spec/plan is not
  re-derived by a planner, it is decomposed.
- **Factory (Droid/Missions)** formalises "agree on the plan before the agent
  writes code" — the plan is an *approval artefact*, kept at the level a human
  would approve (intents and milestones), not a code transcript.
- **Uber AutoCover** splits Planner → Generator → Executor: the planner emits
  *what* to cover, the generator/executor own the code. Its Fixer repairs
  "minimal, reversible edits" — the implementer owns the mechanics.
- **Playwright's planner/generator measurement** (Gary Parker, 2026-11): the
  planner "discloses scope changes" and stays at scenario fidelity; the 43-minute
  generator cost is the tax on *over-verified detail*, which the report argues
  should not be in the plan.
- **Agentless** (SWE-bench) found over-specified patch plans *hurt*: localise →
  repair → validate with minimal planning beats elaborate step plans.

The common thread: **the plan is intent + acceptance, the implementer owns the
how.** Our `PLAN_RULES` inverts this.

## The fix, in one paragraph

Feed the planner the human `plan.md` (the approach already exists) and ask it to
*decompose into logical steps* — one acceptance criterion per step, naming the
files it may touch, and **forbidden to invent API names**. The coder keeps the
"read the real module, use its real API" rule and owns the implementation. A
plan.md is never re-derived; when it is absent or unusable the planner falls back
to deriving from the ACs, and the run records which source it used.

## Risks and their answers

- **The plan.md may be stale or wrong for the task.** The planner still sees the
  ACs and the brief, so a step that contradicts the acceptance criteria must
  fail the verifier; `--replan` forces the derive path; `run.json.plan_src`
  records the source so a wrong plan is attributable.
- **Fewer, coarser steps might lose the "one file per step" safety.** The scope
  guard and the verifier still bound every step; the change is fidelity of the
  instruction, not a widening of scope.
- **Token savings is the wrong goal.** The acceptance is the replay suite: green
  rate must not drop; prompt chars are measured and reported but never the
  success criterion (020's lesson).

## Sources

Attractor/NLSpecs and Factory's plan-first posture: `dark-factory-market-2026.md`.
AutoCover: ICSE-SEIP 2026. Playwright planner/generator measurement:
`self-healing-e2e-2026.md`. Agentless: SWE-bench literature. Our own evidence:
`swarm/prompts.py` (`PLAN_RULES`, `task_block(plan=…)`), `swarm/flow.py`
(`plan_source_hash`), the 007-T9 duplicate-module incident.
