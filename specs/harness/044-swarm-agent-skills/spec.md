# 044 Swarm Agent Skills — Spec

Harness spec (control plane; the queue never runs it).

## Problem

The swarm's agents are built entirely from hardcoded role/goal/backstory in
`swarm/prompts.py` (`_AGENT_COPY`) and `swarm/crew.py`. A factory operator — or a
future user who drops the swarm into their own repo (038) — cannot add, tune or
swap a subagent's skill without editing the harness source. Skills are invisible,
non-portable and impossible to version outside the code.

The swarm already depends on CrewAI, whose `Agent` supports a `skills` list of
`Skill` objects parsed from YAML-frontmatter markdown. The harness never uses it.

## Goal

An external, injectable **skill folder** the swarm auto-discovers and injects
into each agent at build time:

1. A folder `swarm/agents/skills/` (overridable) holds one YAML-frontmatter
   markdown file per subagent role.
2. The filename is the role's skill key (e.g. `coder.md`, `qa.md`,
   `verifier.md`, `planner.md`, `senior.md`).
3. When the swarm builds a core agent, it loads that role's file and appends the
   resulting CrewAI `Skill` objects to the agent's `skills` attribute — additive
   to the existing backstory, never replacing it.
4. A missing file falls back to a built-in default skill template for that role
   (never a hard failure).
5. The repo ships reasonable skills for the core roles (coder, QA, verifier,
   planner, senior) so the factory is useful out of the box.
6. The whole mechanism is off-switchable and configurable (`SWARM_SKILLS=0`,
   `SWARM_SKILLS_DIR`), so the swarm runs unchanged with no folder.

This follows the 038-swarm-injection direction (the harness becomes an
injectable, releasable tool): agent skills are the first operator-facing
extension point a future user can populate.

## Acceptance criteria

- **AC-1 — External folder.** Skills live in `swarm/agents/skills/*.md` (or
  `SWARM_SKILLS_DIR` when set). Each file is YAML frontmatter (`name`,
  `description`, optional `metadata`/`allowed-tools`) plus a markdown body. The
  filename is the role key, and the body starts with a `# <Role> Skill` header.
- **AC-2 — Auto-discovery & injection.** When a core agent is built (coder
  step/fix/selfcheck, senior, senior step, QA, verifier, planner), the swarm
  loads that role's skill and appends it to the agent's `skills` list; the
  existing role/goal/backstory are untouched.
- **AC-3 — Default template.** If a role has no skill file, a built-in default
  Skill is produced from a template (frontmatter name/description + minimal
  body); the run continues with no error.
- **AC-4 — Off switch + config.** `SWARM_SKILLS=0` disables loading entirely
  (agents behave exactly as today). `SWARM_SKILLS_DIR` points at a different
  folder. A parse error in an operator file falls back to the default template
  and never fails the run.
- **AC-5 — Shipped skills.** The repo ships `coder`, `qa`, `verifier`,
  `planner`, `senior` skill files with frontmatter + role body.
- **AC-6 — No regression.** `make swarm-test` stays green; agent prompt
  hashes and run behaviour are unchanged (skills append to the `skills` list,
  not the prompt prefix), so enabling the folder is additive.

## Out of scope

- Rewriting the swarm's role/goal/backstory text to read from skills (additive
  only).
- A skill registry / download (CrewAI ships one; the harness reads local files).
- Test-author, conflict and stash roles (future files; not shipped now).
