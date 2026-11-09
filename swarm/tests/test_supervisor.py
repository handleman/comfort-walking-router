"""Supervisor + report tests (015 AC-6, AC-9)."""

from __future__ import annotations

import json
import types
from pathlib import Path

from swarm import report, supervise


def _run_dir(root: Path, name: str, payload: dict) -> Path:
    path = root / "swarm" / "runs" / name
    path.mkdir(parents=True)
    (path / "run.json").write_text(json.dumps(payload))
    return path


def test_supervisor_stops_on_green(tmp_path, monkeypatch):
    runs = tmp_path / "swarm" / "runs"
    runs.mkdir(parents=True)
    calls: list[int] = []

    def runner() -> int:
        calls.append(1)
        _run_dir(tmp_path, f"20260101-00000{len(calls)}-1-a", {"spec": "001", "task": "T1", "status": "green"})
        return 0

    monkeypatch.setattr(supervise, "latest_run", lambda runs=runs: _latest(runs))
    code = supervise.supervise(
        runner=runner,
        runs=runs,
        stop_file=tmp_path / "STOP",
        sleep=lambda _s: None,
        log=lambda _m: None,
        max_rounds=3,
    )
    # Green run means the queue finished → the runner was called once.
    assert code == 0 and len(calls) == 1


def _latest(runs: Path) -> Path | None:
    dirs = sorted(p for p in runs.iterdir() if p.is_dir())
    return dirs[-1] if dirs else None


def test_supervisor_retries_then_marks_retry_later(tmp_path, monkeypatch):
    runs = tmp_path / "swarm" / "runs"
    runs.mkdir(parents=True)
    retry_file = tmp_path / "retry_later.json"
    attempts = {"n": 0}

    def runner() -> int:
        attempts["n"] += 1
        _run_dir(
            tmp_path,
            f"20260101-00000{attempts['n']}-1-a",
            {"spec": "005", "task": "T8", "status": "interrupted"},
        )
        return 1

    sleeps: list[float] = []
    logs: list[str] = []

    def fake_mark(key: str, path: Path = retry_file) -> None:
        data = json.loads(path.read_text()) if path.exists() else {"attempts": {}, "retry_later": []}
        data["retry_later"] = sorted({*data.get("retry_later", []), key})
        path.write_text(json.dumps(data))

    monkeypatch.setattr(supervise, "latest_run", lambda runs=runs: _latest(runs))
    monkeypatch.setattr(supervise, "mark_retry_later", fake_mark)
    monkeypatch.setattr(supervise, "load_attempts", lambda path=None: {})
    monkeypatch.setattr(supervise, "save_attempts", lambda attempts, path=None: None)
    supervise.supervise(
        runner=runner,
        runs=runs,
        stop_file=tmp_path / "STOP",
        sleep=lambda s: sleeps.append(s),
        log=logs.append,
        max_rounds=5,
        max_attempts=3,
        base_delay=1.0,
    )
    assert attempts["n"] == 5
    assert sleeps[0] == 1.0 and 2.0 in sleeps
    assert "retry_later" in retry_file.read_text()


def test_supervisor_stops_on_config_error(tmp_path, monkeypatch):
    runs = tmp_path / "swarm" / "runs"
    runs.mkdir(parents=True)

    def runner() -> int:
        _run_dir(tmp_path, "20260101-000001-1-a", {"spec": "005", "task": "T9", "status": "config_error"})
        return 1

    monkeypatch.setattr(supervise, "latest_run", lambda runs=runs: _latest(runs))
    code = supervise.supervise(
        runner=runner,
        runs=runs,
        stop_file=tmp_path / "STOP",
        sleep=lambda _s: None,
        log=lambda _m: None,
    )
    assert code == 1


def test_supervisor_honours_stop_file(tmp_path):
    stop = tmp_path / "STOP"
    stop.write_text("stop")
    calls: list[int] = []
    code = supervise.supervise(
        runner=lambda: calls.append(1) or 0,
        runs=tmp_path,
        stop_file=stop,
        sleep=lambda _s: None,
        log=lambda _m: None,
    )
    assert code == 0 and calls == []


def test_report_summarizes_cost_and_roles(tmp_path):
    runs = tmp_path / "swarm" / "runs"
    runs.mkdir(parents=True)
    _run_dir(
        tmp_path,
        "20260101-000001-1-a",
        {
            "status": "green",
            "cost": 0.01,
            "fix_rounds": 0,
            "usage": {
                "duration_seconds": 100,
                "by_role": {"coder:step1": {"prompt_tokens": 1000, "completion_tokens": 100, "cost_usd": 0.01}},
            },
        },
    )
    _run_dir(
        tmp_path,
        "20260101-000002-1-a",
        {"status": "needs_human", "reason_code": "qa_gate_missing"},
    )
    summary = report.summarize(report.collect(runs))
    assert summary["runs"] == 2 and summary["green"] == 1
    assert summary["cost_per_green_median"] == 0.01
    assert summary["stop_reasons"] == {"qa_gate_missing": 1}
    assert summary["by_role"]["coder:step1"]["prompt_tokens"] == 1000
    text = report.render(summary)
    assert "cost/green" in text and "qa_gate_missing" in text


def test_outcome_actions():
    assert supervise.Outcome("green").action == "continue"
    assert supervise.Outcome("interrupted").action == "retry"
    assert supervise.Outcome("config_error").action == "stop"
    assert supervise.Outcome("needs_human").action == "stop"
    assert isinstance(types.SimpleNamespace(), object)


def test_retry_later_skips_parked_tasks(tmp_path, monkeypatch):
    from swarm import flow

    runs = tmp_path / "swarm" / "runs"
    runs.mkdir(parents=True)
    (runs / "retry_later.json").write_text(
        json.dumps({"attempts": {}, "retry_later": ["005/T8"]})
    )
    monkeypatch.setattr(flow, "REPO_ROOT", tmp_path)
    assert flow._retry_later_keys() == {"005/T8"}
    assert flow._without_retry_later("005", ["T8", "T9"]) == ["T9"]
    # Never deadlock: a fully parked spec still runs.
    assert flow._without_retry_later("005", ["T8"]) == ["T8"]
