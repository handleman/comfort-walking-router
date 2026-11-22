# 044 Swarm Agent Skills — Plan

## Shape

```
swarm/agents/skills/<role>.md  (YAML frontmatter + body)
        │
        ▼
swarm/tools_skills.py
   ├─ skill_file_for_role(role) → Path | None
   ├─ load_skill_for_role(role) → [Skill] (default template when absent)
   └─ inject_skill_into_agent(role, agent) → agent (append, no-op if SWARM_SKILLS=0)
        │
        ▼
swarm/crew.py  (_coder, _reviewer, _build_verify_crew, _build_plan_crew,
                 _build_senior_step_crew, _build_senior_crew)
   └─ after Agent(...): inject skill → agent.skills
```

## Steps

1. **`swarm/tools_skills.py`** — `SWARM_SKILLS` (default `1`) off switch,
   `SWARM_SKILLS_DIR` (default `swarm/agents/skills`), role→filename map + name
   fallback, CrewAI `load_skill` parse, built-in default template for missing
   roles, additive inject into `agent.skills`.
2. **Skill files** — ship `coder`, `qa`, `verifier`, `planner`, `senior`
   (`.md` with YAML frontmatter + body). Already created under
   `swarm/agents/skills/`.
3. **Crew wiring** — inject into the six core builders: `_coder` (coder /
   senior by kind), `_reviewer` (qa), `build_verify_crew` (verifier),
   `build_plan_crew` (planner), `build_senior_step_crew` and
   `build_senior_crew` (senior).
4. **Tests** — discovery, loading, default fallback, off switch, additive
   injection; `make swarm-test` green; prompt-prefix hashes unchanged.
5. **Docs** — `GLOSSARY.md`, `docs/reference.md`, `swarm/README.md`, changelog.

## Risks

- **CrewAI API drift.** `skills` attribute + `load_skill` are current-CrewAI;
  guarded and tested (fallback to no skill on error).
- **Operator file parse error.** Falls back to the default template; never
  fails the run.
- **Additivity.** Injection appends to `agent.skills`, not the backstory, so
  prompt prefixes are untouched (tests assert).
- **Missing skill.** Default template keeps runs alive with no operator files.
