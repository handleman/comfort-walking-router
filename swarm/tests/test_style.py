"""Style repair tests (016 follow-up): a Prettier/ESLint slip is not coder work."""

from __future__ import annotations

from swarm import style


def test_style_gate_needs_a_sole_style_failure():
    gates = {"npm --prefix frontend run lint": 1}
    tails = {"npm --prefix frontend run lint": "Code style issues found in the above file"}
    assert style.style_gate(gates, tails) == "npm --prefix frontend run lint"


def test_style_gate_ignores_a_type_error():
    """A red type check is a code problem: the formatter cannot fix it."""
    gates = {"npm --prefix frontend run lint": 1, "npm --prefix frontend run check": 1}
    tails = {
        "npm --prefix frontend run lint": "Code style issues found in the above file",
        "npm --prefix frontend run check": "Error: Cannot find name 'positionStore'.",
    }
    assert style.style_gate(gates, tails) is None


def test_style_gate_ignores_a_parse_error():
    gates = {"npm --prefix frontend run lint": 1}
    tails = {
        "npm --prefix frontend run lint": (
            "  149:2  error  Parsing error: Declaration or statement expected"
        )
    }
    assert style.style_gate(gates, tails) is None


def test_style_gate_ignores_an_unfixable_eslint_rule():
    """`no-unused-vars` is a code problem: `eslint --fix` cannot repair it."""
    gates = {"npm --prefix frontend run lint": 1}
    tails = {
        "npm --prefix frontend run lint": (
            "  1:7  error  'x' is assigned a value but never used  "
            "@typescript-eslint/no-unused-vars"
        )
    }
    assert style.style_gate(gates, tails) is None


def test_style_gate_accepts_an_auto_fixable_eslint_rule():
    gates = {"npm --prefix frontend run lint": 1}
    tails = {
        "npm --prefix frontend run lint": (
            "  3:7  error  'total' is never reassigned. Use 'const' instead  "
            "@typescript-eslint/prefer-const"
        )
    }
    assert style.style_gate(gates, tails) == "npm --prefix frontend run lint"


def test_style_gate_ignores_non_style_gates():
    gates = {"npm --prefix frontend test -- --run": 1}
    tails = {"npm --prefix frontend test -- --run": "FAIL src/lib/x.test.ts"}
    assert style.style_gate(gates, tails) is None


def test_style_gate_ignores_a_green_lint_gate():
    gates = {"npm --prefix frontend run lint": 0}
    assert style.style_gate(gates, {}) is None


def test_style_fix_is_off_without_a_command(monkeypatch):
    monkeypatch.delenv("SWARM_STYLE_FIX_COMMAND", raising=False)
    monkeypatch.delenv("SWARM_STYLE_FIX", raising=False)
    assert style.enabled() is False
    monkeypatch.setenv("SWARM_STYLE_FIX_COMMAND", "npm --prefix frontend run lint:fix")
    assert style.enabled() is True
    monkeypatch.setenv("SWARM_STYLE_FIX", "0")
    assert style.enabled() is False


def test_scope_gate_is_not_a_style_gate():
    gates = {"scope": 1}
    tails = {"scope": "VIOLATIONS: ['docs/x.md']"}
    assert style.style_gate(gates, tails) is None


class _Stub:
    def __init__(self) -> None:
        import types

        self._baseline: dict[str, str] = {}
        self.state = types.SimpleNamespace(style_autofix={})


def test_autofix_style_runs_the_formatter_and_records_it(monkeypatch):
    """The harness, not a coder round, repairs a style-only failure."""
    from swarm import flow, tools_guarded

    monkeypatch.setenv("SWARM_STYLE_FIX", "1")
    monkeypatch.setenv("SWARM_STYLE_FIX_COMMAND", "npm --prefix frontend run lint:fix")
    calls: list[tuple[str, str]] = []

    class FakeShell:
        def __init__(self, agent_role: str = "") -> None:
            self.agent_role = agent_role

        def _run(self, command: str) -> str:
            calls.append((self.agent_role, command))
            return "formatted"

    monkeypatch.setattr(tools_guarded, "ShellTool", FakeShell)
    monkeypatch.setattr(tools_guarded, "_git_changed", lambda: ["frontend/src/lib/x.ts"])
    monkeypatch.setattr(tools_guarded, "run_delta", lambda baseline: ["frontend/src/lib/x.ts"])

    stub = _Stub()
    gates = {"npm --prefix frontend run lint": 1}
    transcript = (
        "$ npm --prefix frontend run lint\nexit=1\n"
        "Code style issues found in the above file. Run Prettier to fix.\n"
    )
    assert flow.SwarmFlow._autofix_style(stub, gates, transcript) is True
    assert calls == [("harness-style", "npm --prefix frontend run lint:fix")]
    assert stub.state.style_autofix["gate"] == "npm --prefix frontend run lint"
    assert stub.state.style_autofix["files"] == []


def test_autofix_style_stays_out_of_a_code_failure(monkeypatch):
    from swarm import flow, tools_guarded

    monkeypatch.setenv("SWARM_STYLE_FIX", "1")
    monkeypatch.setenv("SWARM_STYLE_FIX_COMMAND", "npm --prefix frontend run lint:fix")
    calls: list[str] = []

    class FakeShell:
        def __init__(self, agent_role: str = "") -> None:
            self.agent_role = agent_role

        def _run(self, command: str) -> str:
            calls.append(command)
            return "formatted"

    monkeypatch.setattr(tools_guarded, "ShellTool", FakeShell)

    stub = _Stub()
    gates = {"npm --prefix frontend run check": 1}
    transcript = "$ npm --prefix frontend run check\nexit=1\nError: Cannot find name 'x'.\n"
    assert flow.SwarmFlow._autofix_style(stub, gates, transcript) is False
    assert calls == []
