"""Earned-autonomy tests (024): the risk ladder and the merge decision."""

from __future__ import annotations

from pathlib import Path

from swarm import risk


def test_the_risk_ladder():
    assert risk.classify(["docs/runbooks/overnight-runs.md"]) == 0
    assert risk.classify(["README.md"]) == 0
    assert risk.classify(["tests/test_x.py"]) == 1
    assert risk.classify(["frontend/e2e/walk.spec.ts"]) == 1
    assert risk.classify(["app/scoring.py"]) == 2
    assert risk.classify(["frontend/src/App.svelte"]) == 2
    assert risk.classify(["contracts/route.json"]) == 2
    assert risk.classify(["swarm/flow.py"]) == 3
    assert risk.classify(["specs/001/spec.md"]) == 3
    assert risk.classify(["requirements.txt"]) == 3
    assert risk.classify(["pyproject.toml"]) == 3
    assert risk.classify(["app/migrations/001.sql"]) == 3
    assert risk.classify([]) == 3


def test_sensitive_briefs_are_control_even_on_a_logic_path():
    assert risk.classify(["app/x.py"], "add auth token rotation") == 3
    assert risk.classify(["app/x.py"], "payment webhook") == 3


def test_unknown_paths_are_control():
    assert risk.classify(["scripts/new_tool.py"]) == 3


def test_earned_auto_merge_only_for_low_risk_green_work():
    def decision(changed, *, autonomy=True, max_class=1, gates=None, verdict="pass", blocked=False):
        return risk.decision(
            changed=changed,
            brief="",
            gates=gates if gates is not None else {"pytest -q": 0},
            review_verdict=verdict,
            verifier_blocked=blocked,
            autonomy=autonomy,
            max_class=max_class,
        )

    assert decision(["docs/x.md"])["auto_merge"] is True
    assert decision(["tests/test_x.py"])["auto_merge"] is True
    assert decision(["app/x.py"])["auto_merge"] is False
    assert decision(["swarm/x.py"])["auto_merge"] is False
    assert decision(["docs/x.md"], autonomy=False)["auto_merge"] is False
    assert decision(["docs/x.md"], gates={"pytest -q": 1})["auto_merge"] is False
    assert decision(["docs/x.md"], verdict="blocked")["auto_merge"] is False
    assert decision(["docs/x.md"], blocked=True)["auto_merge"] is False
    assert decision(["docs/x.md"], max_class=0)["auto_merge"] is True
    assert decision(["tests/test_x.py"], max_class=0)["auto_merge"] is False


def test_the_decision_explains_itself():
    info = risk.decision(
        changed=["app/x.py"], brief="", gates={"pytest -q": 0},
        review_verdict="pass", verifier_blocked=False, autonomy=True, max_class=1,
    )
    assert info["class"] == 2 and info["label"] == "logic"
    assert "class 2 > max 1" in info["reason"]
    assert info["gates_green"] is True


def test_the_flow_gates_the_hold_on_the_decisions():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert 'os.getenv("SWARM_AUTONOMY", "0")' in source
    assert 'payload["autonomy"] = autonomy' in source
    assert 'not autonomy["auto_merge"]' in source


def test_the_human_log_and_report_show_autonomy():
    from swarm import report
    from swarm.humanlog import format_human_report

    payload = {
        "spec": "001", "task": "T1", "status": "green",
        "autonomy": {"class": 1, "label": "tests", "auto_merge": True, "reason": "earned"},
    }
    text = format_human_report(payload, [])
    assert "risk class 1 (tests): auto-merged" in text

    summary = report.summarize([
        {"status": "green", "fix_rounds": 0, "autonomy": {"class": 1, "auto_merge": True}},
        {"status": "green", "fix_rounds": 0, "autonomy": {"class": 2, "auto_merge": False}},
    ])
    assert summary["auto_merged"] == 1
    assert summary["autonomy"] == {"class 1": 1, "class 2": 1}
    assert "auto-merged 1" in report.render(summary)
