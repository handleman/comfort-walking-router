# 045 Swarm Agent Dedup — Tasks

Each task is atomic and maps to exactly one acceptance criterion.

- [x] T1 (AC-1): `swarm/crew.py` — extract `_senior_agent(task, kind)` internal builder that builds the common `Agent(role, goal, backstory, llm=senior_llm(), tools=_tools(role=...), max_iter, agent_copy(...), stack_hint(...))` used by both `build_senior_step_crew` and `build_senior_crew`. Ensure `max_iter=12` for `senior_step` and `max_iter=16` for `senior`.
- [x] T2 (AC-2): `swarm/crew.py` — extract `_conflict_resolver_agent(kind)` internal builder that builds the common `Agent(role, goal, backstory, llm=conflict_llm(allow_paid=True), tools=[TrimmedFileReadTool(), EditTool()], max_iter=10, agent_copy(...), SCOPE_RULE)` used by both `build_conflict_crew` and `build_stash_crew`, with `kind` selecting merge vs stash goal and backstory text.
- [x] T3 (AC-3): Tests — `make swarm-test` stays green (`758` tests). All existing assertions over `build_senior_crew`, `build_senior_step_crew`, `build_conflict_crew`, `build_stash_crew` (structure, `max_iter`, tools, skill injection) pass unchanged.
- [x] T5 (AC-5): Docs — `AGENTS.md`, `GLOSSARY.md`, `docs/reference.md` updated to note the internal shared builders.
- [x] T6 (AC-6): Skills — verify that 044 skill injection appends the `senior` skill to both `build_senior_crew` and `build_senior_step_crew` agents (same skill name) and does not break for the conflict resolvers (default template fallback).