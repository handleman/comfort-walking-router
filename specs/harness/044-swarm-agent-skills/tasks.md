# 044 Swarm Agent Skills — Tasks

Each task is atomic and maps to exactly one acceptance criterion.

- [ ] T1 (AC-1): `swarm/tools_skills.py` — `SWARM_SKILLS` (default `1`) off switch, `SWARM_SKILLS_DIR` (default `swarm/agents/skills`), role→filename map + name fallback, CrewAI `load_skill` parse, built-in default template for missing roles, additive inject into `agent.skills`. Unit tests for discovery, loading, default fallback, off switch, additive injection.
- [ ] T2 (AC-2): Skill files — ship `coder`, `qa`, `verifier`, `planner`, `senior` (`.md` with YAML frontmatter + body) under `swarm/agents/skills/`.
- [ ] T3 (AC-2): Crew wiring — inject into the six core builders: `_coder` (coder / senior by kind), `_reviewer` (qa), `build_verify_crew` (verifier), `build_plan_crew` (planner), `build_senior_step_crew` and `build_senior_crew` (senior).
- [ ] T4 (AC-4, AC-6): Tests — `make swarm-test` stays green; agent prompt-prefix hashes and run behaviour are unchanged (skills append to the `skills` list, not the prompt prefix), so enabling the folder is additive.
- [ ] T5 (AC-5): Docs — `GLOSSARY.md` entry for "Agent Skill", `docs/reference.md` config keys (`SWARM_SKILLS`, `SWARM_SKILLS_DIR`), `swarm/README.md` run section mention, `changelog.md` entry (already done), `AGENTS.md` clarifying questions (already done).