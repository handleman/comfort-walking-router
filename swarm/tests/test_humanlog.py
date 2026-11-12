"""Tests for the human-readable run report (018).

The report is the operator's copy-pasteable answer to "why did this stop?".
It must name the stop reason, the failing gates and the reviewer's verdict —
and the dashboard screen and the on-disk file must be the same text.
"""

import json

from swarm.humanlog import (
    format_human_report,
    latest_run_dir,
    write_human_report,
)


def _payload(**overrides):
    payload = {
        "spec": "014-walk-guidance-ux",
        "task": "T1",
        "status": "needs_human",
        "reason_code": "no_progress",
        "review_verdict": "unknown",
        "gates": {"pytest -q": 1, "ruff check .": 1, "mypy app tests": 0},
        "review_tail": "verdict was never declared",
        "changed_files": ["app/geocoding.py", "tests/test_geocoding.py"],
        "usage": {
            "total_tokens": 1_679_352,
            "cost_usd": 0.0,
            "duration_seconds": 3040,
            "llm_calls": 229,
            "by_role": {
                "coder:fix1": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "cost_usd": 0.0,
                }
            },
        },
    }
    payload.update(overrides)
    return payload


def test_report_names_the_stop_reason_and_failing_gates():
    text = format_human_report(_payload(), [], run_name="run-1")
    assert "014-walk-guidance-ux T1" in text
    assert "reason_code: no_progress" in text
    assert "reviewer verdict: unknown" in text
    assert "pytest -q 1" in text
    assert "mypy app tests 0" in text
    assert "app/geocoding.py" in text


def test_report_is_plain_text_without_ansi_marks():
    """The file is meant to be pasted into a ticket: no escape sequences."""
    text = format_human_report(_payload(), [])
    assert "\x1b[" not in text
    assert "\r" not in text


def test_report_shows_the_reason_code_for_a_budget_stop():
    payload = _payload(
        status="budget_exhausted",
        reason_code="budget_exhausted",
        budget_note="task 014-walk-guidance-ux/T10: time budget exceeded: 2039s > 1800s",
    )
    text = format_human_report(payload, [])
    assert "budget_exhausted" in text
    assert "time budget exceeded: 2039s > 1800s" in text


def test_report_includes_qa_error_key_lines():
    payload = _payload(
        qa_report={
            "verdict": "blocked",
            "gates": [
                {
                    "command": "pytest -q",
                    "exit": 1,
                    "errors": ["tests/test_geocoding.py:39: AssertionError"],
                }
            ],
        }
    )
    text = format_human_report(payload, [])
    assert "AssertionError" in text


def test_report_lists_events():
    events = [{"type": "task_done", "agent": "Test Coder", "text": "done"}]
    text = format_human_report(_payload(), events)
    assert "task_done" in text
    assert "Test Coder" in text


def test_write_human_report_writes_a_file_next_to_the_run(tmp_path):
    run_dir = tmp_path / "20261112-004043-1092-2c1c"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(json.dumps(_payload()))
    (run_dir / "events.jsonl").write_text(
        json.dumps({"type": "task_done", "text": "done"}) + "\n"
    )

    path = write_human_report(run_dir)

    assert path is not None
    assert path.name == "human_log.txt"
    text = path.read_text()
    assert "014-walk-guidance-ux T1" in text
    assert "reason_code: no_progress" in text


def test_write_human_report_returns_none_without_a_run_json(tmp_path):
    assert write_human_report(tmp_path) is None


def test_latest_run_dir_picks_the_newest(tmp_path):
    for name in ("20260101-000000-1-aaaa", "20260102-000000-2-bbbb"):
        (tmp_path / name).mkdir()
    assert latest_run_dir(tmp_path).name == "20260102-000000-2-bbbb"


def test_latest_run_dir_is_none_when_empty(tmp_path):
    assert latest_run_dir(tmp_path) is None


def test_dashboard_screen_and_file_render_the_same_text(tmp_path):
    """The screen (`h`) and the file must not drift apart."""
    from swarm.tui import format_human_report as screen_render

    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(json.dumps(_payload()))
    payload = json.loads((run_dir / "run.json").read_text())

    assert screen_render(payload, []) == format_human_report(payload, [])
