# 045 Swarm Agent Dedup — Spec

Harness spec (control plane; the queue never runs it).

## Problem

The swarm ships 11 agent builders in `swarm/crew.py` that construct distinct
CrewAI agents. Two pairs duplicate agent-construction code with no behavioural
difference beyond a label:

- **Senior step** (`build_senior_step_crew`, kind `senior_step`, max_iter 12)
  vs **Senior fix** (`build_senior_crew`, kind `senior`, max_iter 16). Both build
  a `Senior Developer` agent with identical tools, llm and backstory pattern
  (`_tools(role=...)`, `senior_llm()`, `agent_copy(task, kind)` + `stack_hint`); the
  only deltas are the prompt function (`senior_step_prompt` vs `senior_prompt`) and
  `max_iter`.
- **Merge Conflict Resolver** (`build_conflict_crew`) vs **Stash Conflict Resolver**
  (`build_stash_crew`). Both build a resolver with `conflict_llm(allow_paid=True)`,
  `TrimmedFileReadTool`, `EditTool`, `max_iter=10`, no shell, no gates; only the
  goal/backstory text and the task-description builder differ.

This duplication means a future change to a shared invariant (a tool set, a
disclosure policy, a scope rule) must be edited in two places and can silently
drift. The coder variants (`step`/`fix`/`selfcheck`) already share the `_coder`
factory and are **out of scope** — there is no duplication there.

## Goal

Deduplicate the two duplicated pairs into shared builders, with **zero change to
observable behaviour**:

1. A shared **senior agent factory** that `build_senior_step_crew` and
   `build_senior_crew` call with their own prompt and `max_iter`; the built agent
   is byte-equivalent to today's.
2. A shared **conflict resolver factory** that `build_conflict_crew` and
   `build_stash_crew` call with a `kind` (`merge` / `stash`) that selects goal and
   backstory; the built agent is byte-equivalent to today's.

The public builder names (`build_senior_step_crew`, `build_senior_crew`,
`build_conflict_crew`, `build_stash_crew`) and their signatures stay unchanged so
`flow.py` and every existing test import site keep working.

## Acceptance criteria

- **AC-1 — Senior factory.** `swarm/crew.py` exposes an internal senior agent
  builder that `build_senior_step_crew` and `build_senior_crew` both call. For each
  kind the resulting `Agent` has the same `role`, `goal`, `backstory`, `llm`,
  `tools`, `max_iter` and retry limit as the pre-dedup build. No other module
  changes its call sites.
- **AC-2 — Conflict resolver factory.** `swarm/crew.py` exposes an internal
  resolver builder that `build_conflict_crew` and `build_stash_crew` both call
  with `kind="merge"` / `kind="stash"`. For each kind the resulting `Agent` has
  the same `role`, `goal`, `backstory`, `llm`, `tools`, `max_iter` and retry limit
  as the pre-dedup build.
- **AC-3 — No regression.** `make swarm-test` stays green (`758` tests); every
  existing assertion over `build_senior_crew`, `build_senior_step_crew`,
  `build_conflict_crew`, `build_stash_crew` (structure, `max_iter`, skill
  injection, prompt hashing) passes unchanged.
- **AC-4 — Skills injection unchanged.** The 044 skill injection still appends to
  `agent.skills` for the deduped agents (senior → `senior` skill, both resolvers →
  no shipped skill, default template).

## Out of scope

- Coder variants (`step`/`fix`/`selfcheck`) — already centralized in `_coder`.
- Merging structurally distinct roles (verifier vs QA vs planner vs test author).
- Changing model routing, `max_iter` values, or any prompt text.