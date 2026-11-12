"""Outcome-suite bookkeeping tests (021 T1). No model is called."""

from __future__ import annotations

import json
from pathlib import Path

from swarm.bench import replay


def _result(case: str, *, ok: bool, seconds: int = 100, tokens: int = 1000, fixes: int = 0) -> dict:
    return {
        "ok": ok,
        "case": case,
        "status": "green" if ok else "needs_human",
        "error": "" if ok else "verifier_blocked",
        "duration_seconds": seconds,
        "prompt_tokens": tokens,
        "cached_prompt_tokens": tokens // 10,
        "cost_usd": 0.0,
        "fix_rounds": fixes,
        "gates": {"pytest -q": 0},
        "changed_files": ["app/x.py"],
    }


def test_selected_cases_default_and_override():
    assert replay.selected_cases({}) == replay.DEFAULT_CASES
    assert replay.selected_cases({"SWARM_REPLAY_CASES": "a-T1, b-T2"}) == ("a-T1", "b-T2")
    assert replay.selected_cases({"SWARM_REPLAY_CASES": " , "}) == replay.DEFAULT_CASES


def test_off_env_is_the_020_side_of_the_knobs():
    assert replay.off_env(False) == {}
    assert replay.off_env(True) == {
        "SWARM_STYLE_PRE_QA": "0",
        "SWARM_TESTS_FIRST": "0",
        "SWARM_CODER_ACS": "0",
    }


def test_run_suite_aggregates_and_passes_the_off_overrides(tmp_path: Path):
    calls: list[dict] = []

    def runner(case, **kwargs):
        calls.append(kwargs)
        return _result(case, ok=case.endswith("T2"), seconds=200, tokens=5000, fixes=1)

    suite = replay.run_suite(["a-T1", "b-T2"], repo=tmp_path, off=True, runner=runner)
    totals = suite["totals"]
    assert totals["cases"] == 2 and totals["green"] == 1
    assert totals["green_rate"] == 50.0
    assert totals["duration_p50"] == 200
    assert totals["prompt_tokens"] == 10_000 and totals["cached_prompt_tokens"] == 1_000
    assert totals["fix_rounds"] == 2
    assert calls[0]["env_overrides"] == replay.OFF_ENV
    assert suite["off"] is True


def test_a_runner_exception_is_a_row_not_a_crash(tmp_path: Path):
    def runner(case, **kwargs):
        if case == "boom-T1":
            raise RuntimeError("no models")
        return _result(case, ok=True)

    suite = replay.run_suite(["boom-T1", "ok-T2"], repo=tmp_path, runner=runner)
    assert suite["totals"]["cases"] == 2 and suite["totals"]["green"] == 1
    assert suite["rows"][0]["ok"] is False
    assert "no models" in suite["rows"][0]["error"]


def test_compare_flags_green_changes_and_deltas():
    before = {"rows": [{"case": "a-T1", "ok": True, "duration_seconds": 300, "prompt_tokens": 1000, "fix_rounds": 1}]}
    after = {
        "rows": [
            {"case": "a-T1", "ok": False, "duration_seconds": 200, "prompt_tokens": 900, "fix_rounds": 0},
        ]
    }
    delta = replay.compare(before, after)[0]
    assert delta["green_before"] is True and delta["green_after"] is False
    assert delta["duration_delta"] == -100
    assert delta["tokens_delta"] == -100
    assert delta["fix_rounds_delta"] == -1


def test_render_shows_status_totals_and_the_baseline_delta(tmp_path: Path):
    suite = replay.run_suite(["a-T1"], repo=tmp_path, runner=lambda c, **k: _result(c, ok=True, seconds=120))
    assert "replay suite: 1 cases" in replay.render(suite)
    assert "green 1/1 (100.0%)" in replay.render(suite)
    baseline = json.loads(json.dumps(suite))
    baseline["totals"]["prompt_tokens"] += 500
    text = replay.render(suite, baseline)
    assert "baseline: green 1/1" in text and "green changed" not in text


def test_baseline_roundtrip_records_the_commit(tmp_path: Path):
    suite = replay.run_suite(["a-T1"], repo=tmp_path, runner=lambda c, **k: _result(c, ok=True))
    path = tmp_path / "replay_baseline.json"
    replay.write_baseline(path, suite, repo=Path(__file__).resolve().parents[2])
    payload = json.loads(path.read_text())
    assert payload["cases"] == ["a-T1"]
    assert payload["rows"][0]["case"] == "a-T1"
    assert payload["commit"]


def test_makefile_exposes_the_suite():
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text()
    assert "swarm-replay:" in makefile and "swarm-replay-off:" in makefile
    assert "-m swarm.bench.replay" in makefile
