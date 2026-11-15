"""Risk-label tests (024): the label every run carries, and no autonomy switch."""

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


def test_the_record_is_the_label_and_nothing_else():
    info = risk.record(changed=["frontend/src/App.svelte"], brief="wire walk mode")
    assert info == {"class": 2, "label": "logic"}
    assert risk.record(changed=[]) == {"class": 3, "label": "control"}


def test_there_is_no_autonomy_switch():
    """2026-11-15: the swarm is autonomous; a setting cannot make it stop.

    `--require-approval` is a per-run flag for a deliberate look, not a mode.
    """
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "SWARM_AUTONOMY" not in source
    assert "SWARM_REQUIRE_APPROVAL" not in source
    assert 'payload["risk"] = risk.record' in source
    assert "elif self._require_approval and not approved:" in source


def test_a_green_run_is_never_held_without_the_flag():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "elif self._require_approval and not approved:" in source
    assert 'and not autonomy["' not in source


def test_the_human_log_shows_the_class_without_a_merge_verb():
    from swarm.humanlog import format_human_report

    payload = {
        "spec": "001",
        "task": "T1",
        "status": "green",
        "risk": {"class": 2, "label": "logic"},
    }
    text = format_human_report(payload, [])
    assert "risk class 2 (logic)" in text
    assert "auto-merged" not in text
