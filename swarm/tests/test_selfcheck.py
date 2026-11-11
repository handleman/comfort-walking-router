"""Pre-QA self-check tests (017): the coder passes on type-clean, lint-clean work."""

from __future__ import annotations

import types

import swarm.crew  # noqa: F401 - bind the real ShellTool before any test patches it
from swarm import selfcheck


def test_static_checks_are_recognised():
    assert selfcheck.is_static_check("mypy app tests")
    assert selfcheck.is_static_check("ruff check .")
    assert selfcheck.is_static_check("npm --prefix frontend run check")
    assert selfcheck.is_static_check("npm --prefix frontend run lint")
    assert selfcheck.is_static_check("npm run typecheck")
    assert selfcheck.is_static_check("make lint")


def test_test_suites_are_not_static_checks():
    assert not selfcheck.is_static_check("pytest -q")
    assert not selfcheck.is_static_check("npm --prefix frontend test -- --run")
    assert not selfcheck.is_static_check("npm --prefix frontend run build")
    assert not selfcheck.is_static_check("")


def test_commands_default_to_the_static_subset_of_the_gates():
    gates = [
        "pytest -q",
        "ruff check .",
        "mypy app tests",
        "npm --prefix frontend run check",
        "npm --prefix frontend run lint",
        "npm --prefix frontend test -- --run",
    ]
    assert selfcheck.commands(gates, env={}) == [
        "ruff check .",
        "mypy app tests",
        "npm --prefix frontend run check",
        "npm --prefix frontend run lint",
    ]


def test_explicit_commands_win():
    env = {"SWARM_SELF_CHECK_COMMANDS": "npm --prefix frontend run check;make lint"}
    assert selfcheck.commands(["pytest -q"], env=env) == [
        "npm --prefix frontend run check",
        "make lint",
    ]


def test_the_phase_can_be_switched_off():
    assert selfcheck.enabled(env={}) is True
    assert selfcheck.enabled(env={"SWARM_SELF_CHECK": "0"}) is False


def test_report_leads_with_the_failing_check_and_its_key_lines():
    report = selfcheck.render_report(
        {"npm --prefix frontend run check": 1, "ruff check .": 0},
        {
            "npm --prefix frontend run check": (
                "/repo/frontend/src/lib/navigation/walk.integration.test.ts:156:21\n"
                "Error: Property 'tick' does not exist on type 'PositionProvider'.\n"
            ),
            "ruff check .": "All checks passed!\n",
        },
        ["frontend/src/lib/navigation/walk.integration.test.ts"],
    )
    assert "npm --prefix frontend run check  (exit=1)" in report
    assert "Property 'tick' does not exist on type 'PositionProvider'" in report
    assert "walk.integration.test.ts:156:21" in report
    assert "ruff check . (exit=0)" in report


def _flow_stub(monkeypatch, outputs: dict[str, str]):
    """A SwarmFlow stub whose ShellTool returns canned outputs."""
    from swarm import flow, tools_guarded

    calls: list[tuple[str, str]] = []

    class FakeShell:
        def __init__(
            self,
            agent_role: str = "",
            allow_gates: bool = True,
            run_dir: str = "",
        ) -> None:
            self.agent_role = agent_role
            self.allow_gates = allow_gates
            self.run_dir = run_dir

        def _run(self, command: str) -> str:
            calls.append((self.agent_role, command))
            return outputs.get(command, "exit=0\n")

    monkeypatch.setattr(tools_guarded, "ShellTool", FakeShell)
    monkeypatch.setattr(tools_guarded, "run_delta", lambda baseline: [])
    stub = types.SimpleNamespace(
        state=types.SimpleNamespace(self_check={}, style_autofix={}),
        _baseline={},
        _spec_dir="007-live-position",
        _in_scope_paths=lambda paths: list(paths),
    )
    stub._run_self_check = types.MethodType(flow.SwarmFlow._run_self_check, stub)
    stub._self_check_phase = types.MethodType(flow.SwarmFlow._self_check_phase, stub)
    return stub, calls


def test_self_check_reports_the_red_static_check(monkeypatch):
    from swarm import flow

    monkeypatch.setenv("SWARM_GATE_COMMANDS", "mypy app tests;npm --prefix frontend run check")
    stub, calls = _flow_stub(
        monkeypatch,
        {
            "mypy app tests": "exit=0\nSuccess: no issues found in 53 source files\n",
            "npm --prefix frontend run check": (
                "exit=1\n"
                "Error: Property 'tick' does not exist on type 'PositionProvider'.\n"
            ),
        },
    )
    result = flow.SwarmFlow._run_self_check(stub)
    assert result["red"] == ["npm --prefix frontend run check"]
    assert result["exit"]["mypy app tests"] == 0
    assert "Property 'tick' does not exist" in result["report"]
    # Its own agent role: never counted as QA evidence.
    assert {role for role, _ in calls} == {"harness-selfcheck"}


def test_self_check_is_silent_when_everything_is_green(monkeypatch):
    from swarm import flow

    monkeypatch.setenv("SWARM_GATE_COMMANDS", "mypy app tests")
    stub, _ = _flow_stub(monkeypatch, {"mypy app tests": "exit=0\nSuccess\n"})
    result = flow.SwarmFlow._run_self_check(stub)
    assert result["red"] == []
    assert result["exit"] == {"mypy app tests": 0}


def test_self_check_does_not_run_when_disabled(monkeypatch):
    from swarm import flow

    monkeypatch.setenv("SWARM_SELF_CHECK", "0")
    monkeypatch.setenv("SWARM_GATE_COMMANDS", "mypy app tests")
    stub, calls = _flow_stub(monkeypatch, {"mypy app tests": "exit=1\nboom\n"})
    assert flow.SwarmFlow._run_self_check(stub) == {}
    assert calls == []


def test_red_self_check_hands_the_evidence_to_the_coder(monkeypatch):
    """The coder fixes the type error before QA is ever asked to review."""
    from swarm import flow

    monkeypatch.setenv("SWARM_GATE_COMMANDS", "npm --prefix frontend run check")
    stub, _ = _flow_stub(
        monkeypatch,
        {
            "npm --prefix frontend run check": (
                "exit=1\nError: Property 'tick' does not exist on type 'PositionProvider'.\n"
            )
        },
    )
    kicked: list[tuple[str, str]] = []

    def kick(build, role):
        kicked.append((role, build().tasks[0].description))

    task = types.SimpleNamespace(id="T9", ac_refs=("AC-2",), brief="integration test")
    flow.SwarmFlow._self_check_phase(stub, task, kick)
    assert kicked, "the coder must be asked to fix the red static check"
    role, description = kicked[0]
    assert role == "coder:selfcheck1"
    assert "Property 'tick' does not exist on type 'PositionProvider'" in description
    assert stub.state.self_check["rounds"] == len(kicked)
    assert stub.state.self_check["red"] == ["npm --prefix frontend run check"]


def test_self_check_stops_after_the_bounded_fix_rounds(monkeypatch):
    from swarm import flow
    from swarm.crew import MAX_SELF_CHECK_ROUNDS

    monkeypatch.setenv("SWARM_GATE_COMMANDS", "npm --prefix frontend run check")
    stub, _ = _flow_stub(
        monkeypatch,
        {"npm --prefix frontend run check": "exit=1\nError: Property 'tick' does not exist.\n"},
    )
    kicked: list[str] = []

    def kick(build, role):
        kicked.append(role)

    task = types.SimpleNamespace(id="T9", ac_refs=(), brief="x")
    flow.SwarmFlow._self_check_phase(stub, task, kick)
    assert len(kicked) == MAX_SELF_CHECK_ROUNDS
    assert stub.state.self_check["rounds"] == MAX_SELF_CHECK_ROUNDS


def test_green_self_check_never_kicks_the_coder(monkeypatch):
    from swarm import flow

    monkeypatch.setenv("SWARM_GATE_COMMANDS", "npm --prefix frontend run check")
    stub, _ = _flow_stub(monkeypatch, {"npm --prefix frontend run check": "exit=0\nok\n"})
    kicked: list[str] = []

    def kick(build, role):
        kicked.append(role)

    task = types.SimpleNamespace(id="T9", ac_refs=(), brief="x")
    flow.SwarmFlow._self_check_phase(stub, task, kick)
    assert kicked == []
    assert stub.state.self_check["red"] == []


def test_self_check_never_counts_as_qa_evidence():
    """The pre-QA phase is feedback, not a gate: green still needs QA's own run."""
    from swarm.evidence import gate_evidence

    executions = [
        {
            "agent": "harness-selfcheck",
            "argv": ["mypy", "app", "tests"],
            "exit": 0,
            "changed_after": "h",
            "tail": "Success",
        }
    ]
    gates, _tails, missing = gate_evidence(
        executions=executions,
        commands=["mypy app tests"],
        current_hash="h",
    )
    assert gates == {}
    assert missing == ["mypy app tests"]


def test_selfcheck_crew_runs_no_gates():
    from swarm.crew import build_selfcheck_crew
    from swarm.spec_loader import SpecTask
    from swarm.tools_guarded import ShellTool

    task = SpecTask(id="T9", ac_refs=("AC-2",), brief="integration test")
    crew = build_selfcheck_crew("007-live-position", task, "Error: Property 'tick' does not exist.")
    shells = [tool for tool in crew.agents[0].tools if isinstance(tool, ShellTool)]
    assert [shell.allow_gates for shell in shells] == [False]
    assert "Property 'tick' does not exist" in crew.tasks[0].description
