"""044 Swarm Agent Skills — skill loading, off switch, and prefix stability."""

from __future__ import annotations

from pathlib import Path

import pytest

from swarm import crew
from swarm.prompts import stable_prefix
from swarm.spec_loader import SpecTask
from swarm.tools_skills import (
    load_skill_for_role,
    skills_enabled,
)

TASK = SpecTask(id="T1", ac_refs=("AC-1",), brief="Add `app/routing.py` endpoint.")
SPEC = "001-example-app"


def _count_skills(crew) -> int:
    return len(crew.tasks[0].agent.skills or [])


def test_skills_are_on_by_default() -> None:
    assert skills_enabled() is True


def test_shipped_roles_load_real_files() -> None:
    for role in ("coder", "qa", "verifier", "planner", "senior"):
        skills = load_skill_for_role(role)
        assert skills is not None, f"{role} should load its skill file"
        assert skills[0].frontmatter.name == role
        assert skills[0].disclosure_level == 2  # INSTRUCTIONS


def test_missing_role_falls_back_to_default_template() -> None:
    skills = load_skill_for_role("completely-missing-role")
    assert skills is not None
    assert skills[0].frontmatter.name == "completely-missing-role"
    assert skills[0].disclosure_level == 2


def test_inject_skill_appends_without_replacing() -> None:
    cr = crew.build_senior_crew(SPEC, TASK, "pytest exit=1")
    skills = _count_skills(cr)
    assert skills >= 1
    assert cr.tasks[0].agent.skills[0].frontmatter.name == "senior"


def test_inject_skill_into_senior_step_uses_senior_skill() -> None:
    cr = crew.build_senior_step_crew(SPEC, TASK, "Edit `app/scoring.py`.", 1, 2, "boom")
    skills = _count_skills(cr)
    assert skills >= 1
    assert cr.tasks[0].agent.skills[0].frontmatter.name == "senior"


def test_inject_skill_does_not_change_stable_prefix() -> None:
    """044 AC-6: skills append to agent.skills, never to the prompt prefix/hash."""
    for kind, builder_kwargs in [
        ("senior", {"spec_dir": SPEC, "task": TASK, "qa_report_text": "pytest exit=1"}),
        ("senior_step", {"spec_dir": SPEC, "task": TASK, "step_text": "Edit `app/scoring.py`.", "idx": 1, "total": 2, "last_error": "boom"}),
    ]:
        prefix_without = stable_prefix(TASK, SPEC, kind)
        if kind == "senior":
            built = crew.build_senior_crew(**builder_kwargs)
        else:
            built = crew.build_senior_step_crew(**builder_kwargs)
        prefix_with = stable_prefix(TASK, SPEC, kind)
        assert prefix_without == prefix_with
        assert built.tasks[0].description.startswith(prefix_with)


def test_off_switch_disables_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_SKILLS", "0")
    # re-import module state is not needed; functions read env at call time
    built = crew.build_senior_crew(SPEC, TASK, "pytest exit=1")
    assert built.tasks[0].agent.skills == []


def test_custom_skills_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SWARM_SKILLS_DIR", str(tmp_path / "skills"))
    # default template should be used when the custom dir has no files
    skills = load_skill_for_role("coder")
    assert skills is not None
    assert skills[0].frontmatter.name == "coder"
    assert skills[0].frontmatter.metadata["version"] == "0.1-default"
