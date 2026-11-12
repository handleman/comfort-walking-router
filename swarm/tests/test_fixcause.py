"""Fix-cause telemetry tests (021 T2): label the round mechanically."""

from __future__ import annotations

from pathlib import Path

from swarm import fixcause


def _report(*, errors: list[str], exit_code: int = 1, command: str = "pytest -q") -> dict:
    return {
        "gates": [
            {"command": command, "exit": exit_code, "errors": errors, "tail": "\n".join(errors)},
        ]
    }


def test_command_kind_distinguishes_ruff_check_from_npm_check():
    assert fixcause.command_kind("pytest -q") == "test"
    assert fixcause.command_kind("npm --prefix frontend test -- --run") == "test"
    assert fixcause.command_kind("ruff check .") == "lint"
    assert fixcause.command_kind("npm --prefix frontend run lint") == "lint"
    assert fixcause.command_kind("npm --prefix frontend run check") == "type"
    assert fixcause.command_kind("mypy app tests") == "type"
    assert fixcause.command_kind("make lint") == "lint"


def test_a_type_gate_is_a_type_round_and_outranks_a_failing_test():
    gates = {"npm --prefix frontend run check": 1, "npm --prefix frontend test -- --run": 1}
    report = _report(errors=["walk.integration.test.ts:156:21 Property 'tick' does not exist on type"])
    assert fixcause.classify(gates=gates, report=report, verdict="blocked", reason="")["cause"] == "type"


def test_a_test_gate_with_assertions_is_a_test_round():
    report = _report(errors=["FAIL src/lib/x.test.ts", "AssertionError: expected 1 to equal 2"])
    assert fixcause.classify(gates={"npm test -- --run": 1}, report=report, verdict="blocked")["cause"] == "test"


def test_a_test_gate_with_only_type_lines_is_still_a_type_round():
    report = _report(errors=["ts(2322): Type 'string' is not assignable to type 'number'"])
    assert fixcause.classify(gates={"npm test -- --run": 1}, report=report, verdict="blocked")["cause"] == "type"


def test_only_lint_is_a_lint_round():
    report = _report(errors=["I001 Import block is un-sorted", "prettier --check"])
    assert fixcause.classify(gates={"ruff check .": 1}, report=report, verdict="blocked")["cause"] == "lint"


def test_a_round_that_changed_nothing_is_evidence():
    assert fixcause.classify(gates={"pytest -q": 1}, changed=False)["cause"] == "evidence"


def test_a_verifier_block_is_a_scenario_round():
    assert (
        fixcause.classify(gates={"pytest -q": 0}, verifier_blocked=True)["cause"] == "scenario"
    )


def test_an_unknown_verdict_is_a_verdict_round_not_code_work():
    assert fixcause.classify(gates={"pytest -q": 1}, verdict="unknown")["cause"] == "verdict"
    assert fixcause.classify(gates={"pytest -q": 0}, verdict="blocked")["cause"] == "verdict"
    assert fixcause.classify(gates={"pytest -q": 1}, verdict="blocked", missing=["mypy"])["cause"] == "evidence"


def test_classify_returns_the_evidence_it_used():
    row = fixcause.classify(gates={"pytest -q": 1, "scope": 0}, report=_report(errors=[]), verdict="blocked")
    assert row == {
        "cause": "test",
        "phase": "fix",
        "gates": ["pytest -q"],
        "changed": True,
        "verdict": "blocked",
    }


def test_the_flow_records_every_repair_phase():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "fix_rounds_detail" in source
    for phase in ('phase="fix"', 'phase="senior"', 'phase="verify"', 'phase="selfcheck"'):
        assert phase in source
    assert '"fix_rounds_detail": self.state.fix_rounds_detail'.replace('"', '"') in source


def test_report_aggregates_causes_phases_and_changed_rounds():
    from swarm import report

    rows = [
        {
            "status": "green",
            "fix_rounds": 2,
            "usage": {"duration_seconds": 100},
            "fix_rounds_detail": [
                {"cause": "lint", "phase": "fix", "changed": True},
                {"cause": "evidence", "phase": "fix", "changed": False},
                {"cause": "type", "phase": "selfcheck", "changed": True},
            ],
            "self_check": {"rounds": 1, "hit": True},
            "verifier": {"verdict": "pass", "hit": False},
        }
    ]
    summary = report.summarize(rows)
    assert summary["fix_rounds_total"] == 3
    assert summary["fix_rounds_changed"] == 2
    assert summary["fix_causes"] == {"lint": 1, "evidence": 1, "type": 1}
    assert summary["fix_phases"] == {"fix": 2, "selfcheck": 1}
    assert summary["self_check_hits"] == 1 and summary["verifier_runs"] == 1
    text = report.render(summary)
    assert "repair rounds: 3 (2 changed the delta, 1 changed nothing)" in text
    assert "causes: lint=1, evidence=1, type=1" in text
    assert "verification: self-check 1/1 hit, verifier 0/1 hit" in text
