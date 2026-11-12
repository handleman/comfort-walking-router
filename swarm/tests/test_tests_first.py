"""Tests-first phase tests (021 T4). No model is called."""

from __future__ import annotations

from pathlib import Path

from swarm import tests_first


def test_enabled_is_off_by_default_and_accepts_truthy_values():
    assert tests_first.enabled({}) is False
    assert tests_first.enabled({"SWARM_TESTS_FIRST": "1"}) is True
    assert tests_first.enabled({"SWARM_TESTS_FIRST": "true"}) is True
    assert tests_first.enabled({"SWARM_TESTS_FIRST": "0"}) is False


def test_is_test_path_covers_the_layouts_this_repo_uses():
    assert tests_first.is_test_path("tests/test_scoring.py")
    assert tests_first.is_test_path("frontend/src/lib/snap.test.ts")
    assert tests_first.is_test_path("frontend/e2e/walk-mode.spec.ts")
    assert tests_first.is_test_path("app/test_helpers.py")
    assert tests_first.is_test_path("frontend/src/lib/navigation/walk.integration.test.ts")
    assert not tests_first.is_test_path("app/scoring.py")
    assert not tests_first.is_test_path("frontend/src/App.svelte")
    assert not tests_first.is_test_path("frontend/src/lib/contest.ts")


def test_command_for_picks_the_project_gate_for_the_area():
    gates = ["pytest -q", "ruff check .", "npm --prefix frontend test -- --run"]
    assert tests_first.command_for(["tests/test_x.py"], gates) == "pytest -q"
    assert (
        tests_first.command_for(["frontend/src/x.test.ts"], gates)
        == "npm --prefix frontend test -- --run"
    )
    assert tests_first.command_for(["tests/test_x.py"], []) == "pytest -q"


def test_freeze_blocks_writes_and_clears():
    tests_first.freeze(["tests/test_x.py"], {"tests/test_x.py": "def test_x(): pass\n"})
    assert tests_first.is_frozen("tests/test_x.py")
    assert not tests_first.is_frozen("app/scoring.py")
    assert "tests/test_x.py" in tests_first.frozen_note()
    tests_first.clear()
    assert tests_first.frozen_note() == ""


def test_the_tool_layer_refuses_a_frozen_test():
    from swarm.tools_guarded import EditTool

    tests_first.freeze(["tests/test_x.py"], {"tests/test_x.py": "old\n"})
    try:
        out = EditTool()._run("tests/test_x.py", "old", "new")
    finally:
        tests_first.clear()
    assert "frozen test" in out


def test_the_test_author_may_only_write_tests():
    from swarm.tools_guarded import CreateTool

    assert "tests only" in CreateTool(test_only=True)._run("app/scoring.py", "x = 1\n")
    assert "tests only" in CreateTool(test_only=True)._run("frontend/src/App.svelte", "x")


def test_the_test_author_crew_has_no_shell_and_no_gates():
    from swarm.crew import build_test_author_crew
    from swarm.spec_loader import SpecTask
    from swarm.tools_guarded import ShellTool

    task = SpecTask(id="T2", ac_refs=("AC-2",), brief="Add `app/scoring.py`.")
    crew = build_test_author_crew("001-example-app", task, "- AC-2 — score it.")
    tools = crew.agents[0].tools
    assert [a.role for a in crew.agents] == ["Test Author"]
    assert not any(isinstance(t, ShellTool) for t in tools)
    assert all(getattr(t, "test_only", False) for t in tools if t.name.startswith("Repo"))


def test_the_flow_runs_the_phase_before_the_steps_and_records_it():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "self._tests_first_phase(task, _kickoff)" in source
    assert '"tests_first": self.state.tests_first' in source
    # the freeze is cleared at task start, never leaked across tasks
    assert "_tests_first.clear()" in source


def test_the_step_prompt_tells_the_coder_the_tests_are_frozen():
    from swarm.prompts import step_prompt
    from swarm.spec_loader import SpecTask

    task = SpecTask(id="T2", ac_refs=("AC-2",), brief="Add `app/scoring.py`.")
    tests_first.freeze(["tests/test_scoring.py"], {"tests/test_scoring.py": "x\n"})
    try:
        text = step_prompt(task, "001-example-app", "Edit `app/scoring.py`.", 1, 2)
    finally:
        tests_first.clear()
    assert "frozen" in text and "tests/test_scoring.py" in text
