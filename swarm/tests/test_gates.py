"""Gate selection tests (020 T5): narrow the inner loop, never the green."""

from __future__ import annotations

from swarm import gates

FULL = [
    "pytest -q",
    "ruff check .",
    "mypy app tests",
    "npm --prefix frontend run check",
    "npm --prefix frontend run lint",
    "npm --prefix frontend test -- --run",
]


def _select(changed, commands=None, **kwargs):
    return gates.select_gates(changed, commands or FULL, **kwargs)


def test_backend_delta_selects_backend_gates_only():
    selected, skipped = _select(["app/scoring.py", "tests/test_scoring.py"])
    assert selected == ["pytest -q", "ruff check .", "mypy app tests"]
    assert skipped == [
        "npm --prefix frontend run check",
        "npm --prefix frontend run lint",
        "npm --prefix frontend test -- --run",
    ]


def test_frontend_delta_selects_frontend_gates_only():
    selected, skipped = _select(["frontend/src/App.svelte"])
    assert selected == [
        "npm --prefix frontend run check",
        "npm --prefix frontend run lint",
        "npm --prefix frontend test -- --run",
    ]
    assert "pytest -q" in skipped


def test_a_mixed_delta_selects_everything_touched():
    selected, _ = _select(["app/main.py", "frontend/src/App.svelte"])
    assert selected == FULL


def test_an_unmapped_path_fails_open():
    selected, skipped = _select(["scripts/new_tool.py", "app/scoring.py"])
    assert selected == FULL and skipped == []
    assert _select(["pyproject.toml"])[0] == FULL


def test_empty_delta_or_disabled_selection_is_the_full_suite():
    assert _select([]) == (FULL, [])
    selected, skipped = _select(["app/scoring.py"], enabled_flag=False)
    assert selected == FULL and skipped == []


def test_selection_keeps_the_configured_order():
    selected, _ = _select(["frontend/src/lib/x.ts", "app/scoring.py"])
    assert selected == FULL


def test_commands_not_in_the_configured_suite_are_ignored():
    selected, _ = _select(["app/scoring.py"], commands=["mypy app tests"])
    assert selected == ["mypy app tests"]


def test_env_map_overrides_the_default():
    mapping = gates.parse_map("app/**=pytest -q\nfrontend/**=npm --prefix frontend run lint")
    assert mapping == [
        ("app/**", ["pytest -q"]),
        ("frontend/**", ["npm --prefix frontend run lint"]),
    ]
    # SWARM_GATE_MAP is read from the environment at call time
    import os

    os.environ["SWARM_GATE_MAP"] = "app/**=pytest -q"
    try:
        selected, skipped = gates.select_gates(["app/a.py"], FULL)
        assert selected == ["pytest -q"]
        assert "mypy app tests" in skipped
    finally:
        os.environ.pop("SWARM_GATE_MAP", None)


def test_bad_map_lines_are_skipped_not_interpreted():
    assert gates.parse_map("# comment\n\nnonsense\napp/**=pytest -q") == [("app/**", ["pytest -q"])]


def test_record_has_the_shape_run_json_publishes():
    record = gates.record("affected", ["pytest -q"], ["mypy app tests"], {"pytest -q": 0})
    assert record == {
        "mode": "affected",
        "selected": ["pytest -q"],
        "skipped": ["mypy app tests"],
        "affected_gates": {"pytest -q": 0},
    }
    full = gates.record("full", ["pytest -q"], [], {"pytest -q": 0})
    assert "full_gates" in full


def test_flow_state_and_payload_carry_the_selection_record():
    from pathlib import Path

    from swarm.flow import SwarmState

    assert SwarmState().gate_selection == {}
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert '"gate_selection": self.state.gate_selection' in source
    # the green decision refuses an unconfirmed affected round
    assert 'gate_selection.get("mode") == "affected"' in source


def test_bench_counts_the_selected_gates_per_round():
    from swarm.bench import score

    case = {
        "id": "x",
        "spec": "020-harness-efficiency",
        "task": "T1",
        "brief": "Add `app/x.py`.",
        "ac_refs": [],
        "steps": ["Edit `app/x.py`."],
        "changed": ["app/x.py"],
        "files": [],
        "gates": {"pytest -q": 0, "mypy app tests": 0, "npm --prefix frontend run check": 0, "scope": 0},
        "report_fixture": "$ pytest -q\nexit=0\n(clean)",
        "recorded": {"fix_rounds": 0},
    }
    row = score.score_case(case)
    assert row["gates_full"] == 3
    assert row["gates_per_round"] == 2  # app/** → pytest + mypy, no frontend check
