"""Evidence + routing tests (015 AC-1..AC-5, AC-8)."""

from __future__ import annotations

import json
from pathlib import Path

from swarm import evidence


def _rec(argv: list[str], *, exit_code: int = 0, agent: str = "QA Gatekeeper", digest: str = "h", tail: str = "ok"):
    return {
        "agent": agent,
        "argv": argv,
        "exit": exit_code,
        "duration_ms": 5,
        "changed_after": digest,
        "tail": tail,
        "at": "2026-11-09T00:00:00",
    }


def test_gate_evidence_requires_fresh_qa_run():
    commands = ["pytest -q", "ruff check ."]
    executions = [_rec(["pytest", "-q"]), _rec(["ruff", "check", "."], exit_code=1, tail="E1")]
    gates, tails, missing = evidence.gate_evidence(
        executions=executions, commands=commands, current_hash="h"
    )
    assert gates == {"pytest -q": 0, "ruff check .": 1}
    assert missing == []
    assert "E1" in "\n".join(tails)


def test_gate_evidence_rejects_stale_hash_and_coder_runs():
    commands = ["pytest -q"]
    stale = [_rec(["pytest", "-q"], digest="old")]
    _, _, missing = evidence.gate_evidence(executions=stale, commands=commands, current_hash="new")
    assert missing == ["pytest -q"]

    coder = [_rec(["pytest", "-q"], agent="Frontend Coder")]
    _, _, missing = evidence.gate_evidence(executions=coder, commands=commands, current_hash="h")
    assert missing == ["pytest -q"]


def test_gate_evidence_last_run_wins():
    commands = ["pytest -q"]
    executions = [_rec(["pytest", "-q"], exit_code=1), _rec(["pytest", "-q"], exit_code=0)]
    gates, _, missing = evidence.gate_evidence(
        executions=executions, commands=commands, current_hash="h"
    )
    assert gates == {"pytest -q": 0} and missing == []


def test_qa_report_is_bounded_and_carries_failure_output():
    transcript = "$ pytest -q\nexit=1\nFAILED tests/test_x.py::test_y - assert 1 == 2\n"
    report = evidence.qa_report(
        gates={"pytest -q": 1},
        tails=evidence.split_tails(transcript),
        changed=["app/x.py"],
        verdict="blocked",
        reason="test_y fails",
        missing=[],
    )
    assert report["verdict"] == "blocked"
    assert report["gates"][0]["command"] == "pytest -q"
    assert "test_y" in report["gates"][0]["tail"]
    text = evidence.report_text(report)
    assert "exit=1" in text and "test_y" in text and "app/x.py" in text


def test_report_text_puts_failing_gates_first_and_keeps_their_output():
    """007-T9: the vitest failure was cut off by the old 9000 char cap."""
    transcript = (
        "$ pytest -q\nexit=0\n69 passed\n"
        "$ npm --prefix frontend run check\nexit=1\n"
        "/repo/frontend/src/lib/navigation/walk.integration.test.ts:109:7\n"
        "Error: Cannot find name 'positionStore'.\n"
        "$ npm --prefix frontend test -- --run\nexit=1\n"
        "FAIL src/lib/navigation/walk.integration.test.ts\n"
        "AssertionError: expected { x: 0, y: 0 } to deeply equal { x: 10, y: 20 }\n"
    )
    report = evidence.qa_report(
        gates={
            "pytest -q": 0,
            "npm --prefix frontend run check": 1,
            "npm --prefix frontend test -- --run": 1,
        },
        tails=evidence.split_tails(transcript),
        changed=["frontend/src/lib/navigation/walk.integration.test.ts"],
        verdict="blocked",
        reason="type error",
    )
    text = evidence.report_text(report)
    assert text.index("FAILING GATES") < text.index("PASSED GATES")
    assert "Cannot find name 'positionStore'" in text
    assert "AssertionError" in text
    assert "walk.integration.test.ts:109:7" in text
    # The failing output must survive the prompt budget.
    assert len(text) <= evidence.REPORT_MAX_CHARS


def test_extract_error_lines_keeps_position_and_message():
    tail = (
        "/repo/frontend/src/lib/navigation/walk.integration.test.ts:109:7\n"
        "Error: Cannot find name 'positionStore'.\n"
        "\n"
        "====================================\n"
        "svelte-check found 27 errors and 0 warnings in 1 file\n"
    )
    lines = evidence.extract_error_lines(tail)
    assert lines == ["walk.integration.test.ts:109 Error: Cannot find name 'positionStore'."]


def test_shell_log_append_and_read(tmp_path: Path):
    log = tmp_path / evidence.SHELL_LOG
    evidence.append_execution(
        log,
        agent="QA Gatekeeper",
        argv=["pytest", "-q"],
        exit_code=0,
        duration_ms=3,
        changed_after="h",
        tail="ok",
    )
    evidence.append_execution(
        log, agent="QA Gatekeeper", argv=["ruff", "check", "."], exit_code=1,
        duration_ms=4, changed_after="h", tail="bad",
    )
    rows = evidence.read_executions(log)
    assert [r["argv"][0] for r in rows] == ["pytest", "ruff"]
    assert json.loads(json.dumps(rows[0]))["exit"] == 0


def test_signature_normalizes_volatile_parts():
    a = evidence.signature("STEP 2", "FAILED tests/test_x.py::test_y at line 12: assert 1 == 2")
    b = evidence.signature("STEP 2", "FAILED tests/test_x.py::test_y at line 99: assert 1 == 2")
    assert a == b
    assert a != evidence.signature("STEP 3", "FAILED tests/test_x.py::test_y at line 12")


def test_count_skipped():
    assert evidence.count_skipped("69 passed, 21 skipped in 0.2s") == 21
    assert evidence.count_skipped("5 passed") == 0


def test_routing_keeps_paid_for_non_trivial(tmp_path: Path):
    from swarm.routing import classify_step

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "existing.py").write_text("x = 1\n")
    cases = {
        "Edit `app/existing.py` — add error handling": "paid",
        "Create `app/new.py` with the constant": "local",
        "Edit `frontend/src/App.svelte` — render the list": "paid",
        "Edit `app/a.py` and `app/b.py`": "paid",
        "Create `app/parse.py` — implement the parser": "paid",
        "Edit `app/existing.py` — rename": "paid",
    }
    for step, expected in cases.items():
        assert classify_step(step, repo_root=tmp_path).kind == expected, step
    assert classify_step("Create `app/new.py`", repo_root=tmp_path, attempt=2).kind == "paid"
    assert classify_step("Create `app/new.py`", repo_root=tmp_path, enabled=False).kind == "paid"


def test_provider_error_classification():
    from swarm.retry import classify_provider_error

    assert classify_provider_error(RuntimeError("429 rate limit")) == "retryable"
    assert classify_provider_error(RuntimeError("<!DOCTYPE html><html>404</html>")) == "config"
    assert classify_provider_error(RuntimeError("Invalid API key")) == "config"
    assert classify_provider_error(RuntimeError("weird")) == "unknown"
    assert classify_provider_error(RuntimeError("free-models-per-day quota")) == "quota"


def test_gate_evidence_accepts_multiple_agents():
    commands = ["pytest -q", "ruff check ."]
    rows = [
        {"agent": "QA Gatekeeper", "argv": ["pytest", "-q"], "exit": 0, "changed_after": "h"},
        {"agent": "harness-fallback", "argv": ["ruff", "check", "."], "exit": 0, "changed_after": "h"},
    ]
    gates, _, missing = evidence.gate_evidence(
        executions=rows,
        commands=commands,
        current_hash="h",
        agents=("QA Gatekeeper", "harness-fallback"),
    )
    assert missing == [] and gates == {"pytest -q": 0, "ruff check .": 0}
