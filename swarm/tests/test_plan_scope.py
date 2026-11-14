"""Plan-scope guard tests: a step may not borrow another task's file."""

from __future__ import annotations

from pathlib import Path

from swarm import plan_scope


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "specs" / "004-weather-sun"
    spec.mkdir(parents=True)
    (spec / "tasks.md").write_text(
        "- [ ] T2 (AC-2): Auto-rule in `app/preferences.py` with tests in `tests/test_preferences.py`.\n"
        "- [ ] T4 (AC-4): Wire weather into `app/main.py` and `contracts/route.json`.\n"
    )
    return tmp_path


def test_a_step_on_another_tasks_file_is_trimmed(tmp_path):
    repo = _spec(tmp_path)
    steps = [
        "app/preferences.py — add the thresholds",
        "tests/test_preferences.py — add the matrix",
        "app/main.py — wire the weather source",
        "contracts/route.json — add the fields",
    ]
    kept, trimmed = plan_scope.scope_steps(repo, "004-weather-sun", "T2", steps)
    assert kept == steps[:2]
    assert trimmed == steps[2:]


def test_own_steps_are_never_trimmed(tmp_path):
    repo = _spec(tmp_path)
    steps = ["app/preferences.py — add the rule", "tests/test_preferences.py — test it"]
    assert plan_scope.scope_steps(repo, "004-weather-sun", "T2", steps) == (steps, [])


def test_a_plan_that_is_entirely_another_tasks_becomes_one_own_step(tmp_path):
    """The plan cache handed T2 the T4 plan; never run the wrong scope."""
    repo = _spec(tmp_path)
    steps = ["app/main.py — wire it", "contracts/route.json — add fields"]
    kept, trimmed = plan_scope.scope_steps(
        repo, "004-weather-sun", "T2", steps, "Auto-rule in `app/preferences.py` with tests."
    )
    assert len(kept) == 1
    assert "app/preferences.py" in kept[0]
    assert "tests/test_preferences.py" in kept[0]
    assert trimmed == steps


def test_a_task_without_named_files_keeps_a_foreign_plan(tmp_path):
    repo = _spec(tmp_path)
    steps = ["app/main.py — wire it"]
    # T9 is not in tasks.md, so there are no own files to synthesize from.
    kept, trimmed = plan_scope.scope_steps(repo, "004-weather-sun", "T9", steps, "do the thing")
    assert kept == steps and trimmed == []


def test_a_step_target_is_the_first_named_path():
    assert plan_scope.step_target("app/preferences.py — add the rule") == "app/preferences.py"
    assert plan_scope.step_target("no path here") is None


def test_the_flow_applies_the_guard_and_records_it():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "plan_scope.scope_steps(" in source
    assert '"plan_trimmed": self.state.plan_trimmed' in source
