"""Tools for loading and injecting Agent Skills from the swarm/agents/skills/ folder.

This module uses CrewAI's built-in skill loader to read YAML-frontmatter .md files
from `swarm/agents/skills/<role>.md` and return Skill objects that can be appended
to any CrewAI Agent's `skills` attribute.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from crewai.skills.loader import load_skill
from crewai.skills.models import Skill, SkillFrontmatter

# Mapping from agent role strings to the corresponding skill .md filename.
_ROLE_TO_SKILL_FILE: dict[str, str] = {
    "coder": "coder",
    "qa": "qa",
    "qa_gatekeeper": "qa",
    "verifier": "verifier",
    "qa_verifier": "verifier",
    "planner": "planner",
    "senior": "senior",
    "senior_developer": "senior",
    "test_author": "test_author",
    "merge_conflict_resolver": "conflict_resolver",
    "stash_conflict_resolver": "stash_resolver",
}

# Disclosure level constants: 1=METADATA, 2=INSTRUCTIONS, 3=RESOURCES (int Literal)
_DISCLOSURE_INSTRUCTIONS = 2

# Built-in default templates for roles with no operator file.
_DEFAULT_SKILL_TEMPLATES: dict[str, tuple[str, str]] = {
    "coder": (
        "coder",
        ("You implement one micro-step against the task brief with smallest coherent diffs. "
        "Work from real module APIs; never invent functions or fields. "
        "No gates, no network commands. Use Repo Create for new files, Repo Edit for existing. "
        "Output: one line per file changed."),
    ),
    "qa": (
        "qa",
        ("You are the only role that runs the project gates. Run every configured gate, report "
        "each command, exit code, and failure output. List changed files via `git status`. "
        "If no relevant change, verdict BLOCKED. End with exactly `VERDICT: PASS` or "
        "`VERDICT: BLOCKED`."),
    ),
    "verifier": (
        "verifier",
        ("You verify the scenario, not the gates. Read-only: never write a file, never run a "
        "gate, never commit. Check: every brief-named element exists; pieces connect "
        "(endpoint mounted, real imports, contract matches); ACs addressed. Output FINDING/STEP "
        "lines and `VERDICT: PASS|BLOCKED`."),
    ),
    "planner": (
        "planner",
        ("You decompose one spec task into LOGICAL micro-steps (STEP n lines), each mapping to "
        "one acceptance criterion, with at most which files it may touch. Concrete write verbs "
        "only (Create/Add/Remove/Edit/Refactor). Files must appear in the brief. 4-8 steps."),
    ),
    "senior": (
        "senior",
        ("You are the senior escalation: fix COMPLETELY and coherently from QA's gate evidence. "
        "Imports must resolve; sync/async must match; implementations match ABC signatures. "
        "Diagnose type mismatches by reading the real API. Narrow last-resort suppression only "
        "with explanation. Never delete/disable the feature or blanket-suppress."),
    ),
}


def skills_enabled() -> bool:
    """Whether the skill injection is enabled (default on)."""
    return os.getenv("SWARM_SKILLS", "1") != "0"


def skills_dir() -> Path:
    """The folder holding the role skill .md files."""
    return Path(os.getenv("SWARM_SKILLS_DIR", "swarm/agents/skills")).expanduser()


def _disclosure_level() -> int:
    return _DISCLOSURE_INSTRUCTIONS


def _default_skill(role: str) -> list[Skill]:
    """Return a minimal Skill object from the built-in template for `role`."""
    normalized = role.strip().lower().replace(" ", "-").replace("_", "-")
    name, desc = _DEFAULT_SKILL_TEMPLATES.get(
        normalized,
        (
            normalized,
            f"Agent skill for {normalized}: implement the brief with minimal diffs, no gates.",
        ),
    )
    frontmatter = SkillFrontmatter(
        name=name,
        description=desc,
        metadata={"version": "0.1-default"},
    )
    body = f"# {name.title()} Skill\n\n{desc}"
    return [
        Skill(
            frontmatter=frontmatter,
            instructions=body,
            path=skills_dir(),
            disclosure_level=_disclosure_level(),
        )
    ]


def skill_file_for_role(role: str) -> Path | None:
    """Return the Path to the skill .md file for the given role string."""
    if not skills_enabled():
        return None

    normalized = role.strip().lower().replace(" ", "-").replace("_", "-")
    filename = _ROLE_TO_SKILL_FILE.get(normalized, normalized)

    candidate = skills_dir() / f"{filename}.md"
    if candidate.is_file():
        return candidate
    candidate2 = skills_dir() / f"{role}.md"
    if candidate2.is_file():
        return candidate2
    return None


def load_skill_for_role(role: str) -> list[Skill] | None:
    """Load the Skill objects for a given agent role.

    Reads the skill file from the configured skills dir using CrewAI's
    YAML-frontmatter loader and returns a list of Skill objects. Returns the
    built-in default template if no file is found or loading fails.

    Returns ``None`` only when skills are disabled (``SWARM_SKILLS=0``).
    """
    if not skills_enabled():
        return None

    skill_path = skill_file_for_role(role)
    if skill_path is not None:
        try:
            content = skill_path.read_text(encoding="utf-8")
            loaded: list[Skill] = load_skill(content)
            for s in loaded:
                if s.disclosure_level not in (1, _disclosure_level()):
                    s.disclosure_level = _disclosure_level()
            return loaded
        except Exception as exc:  # noqa: BLE001 — never crash the swarm
            print(
                f"[tools_skills] Failed to load skill file for role '{role}': {exc}; using default",
                file=sys.stderr,
            )

    return _default_skill(role)


def inject_skill_into_agent(role: str, agent: object) -> object:
    """Append the role's skill list to an Agent's ``skills`` attribute.

    If skills are disabled (SWARM_SKILLS=0), reset the agent's ``skills`` to an empty list
    so no injection occurs and the agent starts clean. Existing skills are extended;
    a new list is created from the loaded skill(s) otherwise.
    """
    if not skills_enabled():
        agent.skills = []
        return agent

    skills = load_skill_for_role(role)
    if skills is None:
        return agent
    if not hasattr(agent, "skills") or agent.skills is None:
        agent.skills = []
    if isinstance(skills, list):
        agent.skills.extend(skills)
    else:
        agent.skills = [skills]
    return agent