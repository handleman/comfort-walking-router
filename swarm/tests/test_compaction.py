"""Compaction tests (020 T4): bounded prompts, full evidence on disk."""

from __future__ import annotations

import json
from pathlib import Path

from swarm import compaction
from swarm.evidence import qa_report, report_text, split_tails


def _step_output(i: int, total: int, body: str) -> str:
    return f"--- step {i}/{total} ---\n{body}"


def _report(tails: str, exits: dict[str, int], changed: list[str] | None = None) -> dict:
    return qa_report(
        gates=exits,
        tails=split_tails(tails),
        changed=changed or ["app/scoring.py"],
        verdict="fail",
        reason="QA blocked",
    )


# ---- step digests ----


def test_compaction_writes_full_outputs_and_keeps_one_line_per_step(tmp_path: Path):
    outputs = [
        _step_output(1, 2, "Added `app/weather.py` client.\nlong detail " * 50),
        _step_output(2, 2, "Wired it into `app/main.py`.\n" + "more detail " * 50),
    ]
    digest, record = compaction.compact_steps(outputs, tmp_path, enabled_flag=True)

    assert record["mode"] == "digest" and record["enabled"] is True
    assert record["steps_spilled"] == 2
    assert record["chars_saved"] > 0
    assert (tmp_path / "step_outputs" / "step-001.txt").read_text() == outputs[0]
    assert (tmp_path / "step_outputs" / "step-002.txt").read_text() == outputs[1]

    lines = digest.splitlines()
    assert len(lines) == 2
    assert "step 1/2" in lines[0] and "app/weather.py" in lines[0]
    assert "step_outputs/step-001.txt" in lines[0]
    assert "more detail" not in digest  # the prompt gets a digest, not the log


def test_compaction_is_deterministic(tmp_path: Path):
    outputs = [_step_output(1, 1, "Did `app/a.py`.\n" + "x" * 1000)]
    first, _ = compaction.compact_steps(outputs, tmp_path, enabled_flag=True)
    second, _ = compaction.compact_steps(outputs, tmp_path, enabled_flag=True)
    assert first == second


def test_off_switch_restores_the_full_concatenation(tmp_path: Path):
    outputs = ["a" * 500, "b" * 500]
    text, record = compaction.compact_steps(outputs, tmp_path, enabled_flag=False)
    assert text == "\n".join(outputs)
    assert record["enabled"] is False and record["mode"] == "full"
    assert not (tmp_path / "step_outputs").exists()


def test_env_switch_and_bad_threshold(tmp_path: Path):
    assert compaction.enabled({"SWARM_CONTEXT_COMPACT": "0"}) is False
    assert compaction.enabled({"SWARM_CONTEXT_COMPACT": "1"}) is True
    assert compaction.enabled({}) is True
    assert compaction.spill_chars({"SWARM_GATE_SPILL_CHARS": "123"}) == 123
    assert compaction.spill_chars({"SWARM_GATE_SPILL_CHARS": "nonsense"}) == compaction.DEFAULT_SPILL_CHARS


# ---- gate-log spilling ----


def _vitest_tail() -> str:
    """The 007-T9 failure that five fix rounds could not see."""
    return "\n".join(
        [
            " FAIL  src/lib/navigation/walk.integration.test.ts > ticks",
            "frontend/src/lib/navigation/walk.integration.test.ts:156:21",
            "Error: Property 'tick' does not exist on type 'PositionProvider'.",
            *("    at line " + str(n) + " trace context" for n in range(200)),
        ]
    )


def test_long_failing_tail_is_spilled_and_key_lines_survive(tmp_path: Path):
    tail = _vitest_tail()
    report = _report(
        f"$ npm --prefix frontend test -- --run\nexit=1\n{tail}",
        {"pytest -q": 0, "npm --prefix frontend test -- --run": 1},
    )
    before = report_text(report)
    assert "walk.integration.test.ts:156" in before  # the key line is in the report

    spilled, record = compaction.spill_report(report, tmp_path, enabled_flag=True, max_chars=500)
    text = report_text(spilled)

    assert record["gate_logs"], "the failing tail must be spilled"
    entry = record["gate_logs"][0]
    log = tmp_path / entry["path"]
    assert log.exists() and tail[-200:] in log.read_text()
    assert stuck_line(text, "walk.integration.test.ts:156")
    assert "full log: gate_logs/" in text
    # the raw tail is never pasted into the prompt
    assert tail[-300:] not in text


def stuck_line(text: str, needle: str) -> bool:
    return needle in text


def test_short_failing_tail_stays_in_the_report(tmp_path: Path):
    report = _report(
        "$ pytest -q\nexit=1\napp/scoring.py:4: error: boom",
        {"pytest -q": 1},
    )
    spilled, record = compaction.spill_report(report, tmp_path, enabled_flag=True, max_chars=4000)
    assert record["gate_logs"] == []
    assert "app/scoring.py:4" in report_text(spilled)


def test_passing_gate_tail_is_not_spilled(tmp_path: Path):
    report = _report(
        "$ pytest -q\nexit=0\n" + ("ok line " * 500),
        {"pytest -q": 0},
    )
    _spilled, record = compaction.spill_report(report, tmp_path, enabled_flag=True, max_chars=100)
    assert record["gate_logs"] == []
    assert not (tmp_path / "gate_logs").exists()


def test_spill_off_switch_keeps_the_tail(tmp_path: Path):
    tail = _vitest_tail()
    report = _report(f"$ npm --prefix frontend test -- --run\nexit=1\n{tail}", {"npm --prefix frontend test -- --run": 1})
    spilled, record = compaction.spill_report(report, tmp_path, enabled_flag=False)
    assert record["enabled"] is False and record["gate_logs"] == []
    # not spilled: the tail is still in the report object and the key line is
    # rendered (020 AC-5 stops the raw tail being pasted a second time)
    assert spilled["gates"][0]["tail"].endswith(tail[-50:])
    assert "walk.integration.test.ts:156" in report_text(spilled)


def test_two_gates_with_the_same_slug_do_not_overwrite_each_other(tmp_path: Path):
    long = "x" * 3000
    report = _report(
        f"$ pytest -q\nexit=1\n{long}\n$ pytest -q --x\nexit=1\n{long}",
        {"pytest -q": 1, "pytest -q --x": 1},
    )
    _, record = compaction.spill_report(report, tmp_path, enabled_flag=True, max_chars=100)
    paths = [entry["path"] for entry in record["gate_logs"]]
    assert len(paths) == 2 and len(set(paths)) == 2


def test_merge_records_sums_savings_and_collects_logs():
    a = {"enabled": True, "mode": "digest", "chars_saved": 100, "gate_logs": []}
    b = {"enabled": True, "threshold": 2000, "gate_chars_saved": 3000, "gate_logs": [{"path": "gate_logs/x.log"}]}
    merged = compaction.merge_records(a, b)
    assert merged["chars_saved"] == 100
    assert merged["gate_chars_saved"] == 3000
    assert merged["threshold"] == 2000
    assert merged["gate_logs"] == [{"path": "gate_logs/x.log"}]
    assert merged["enabled"] is True


def test_flow_state_carries_the_compaction_record():
    from swarm.flow import SwarmState

    state = SwarmState()
    assert state.compaction == {}
    # the run payload is the source the operator reads the record from
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert '"compaction": self.state.compaction' in source


def test_report_json_stays_serialisable_after_spilling(tmp_path: Path):
    report = _report(
        "$ pytest -q\nexit=1\n" + "z" * 3000,
        {"pytest -q": 1},
    )
    spilled, _ = compaction.spill_report(report, tmp_path, enabled_flag=True, max_chars=100)
    payload = json.loads(json.dumps(spilled))
    assert payload["spilled"] is True
