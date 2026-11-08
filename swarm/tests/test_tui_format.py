import json

from swarm.tui import (
    fmt_cost,
    fmt_duration,
    fmt_tokens,
    format_gates,
    format_metrics,
    format_recent,
    pct,
    queue_marks,
    scan_runs,
    status_mark,
    status_style,
)


def test_number_formatting():
    assert fmt_tokens(0) == "0"
    assert fmt_tokens(999) == "999"
    assert fmt_tokens(12_345) == "12.3k"
    assert fmt_tokens(2_100_000) == "2.1M"
    assert fmt_cost(0) == "$0"
    assert fmt_cost(None) == "unknown"
    assert fmt_cost(0.0004) == "$0.0004"
    assert fmt_cost(1.5) == "$1.50"


def test_duration_formatting():
    assert fmt_duration(None) == "-"
    assert fmt_duration(9) == "9s"
    assert fmt_duration(125) == "2m05s"
    assert fmt_duration(3725) == "1h02m"


def test_pct_is_bounded():
    assert pct(5, 10) == "50.0%"
    assert pct(1, 0) == "off"
    assert pct(1e9, 1) == "999.0%"


def test_status_styles_cover_new_phase1_statuses():
    for status in ("budget_exhausted", "preflight_failed", "quota_exhausted", "green"):
        assert status_style(status) != "white"
    assert status_mark("green")[0] == "✓"
    assert status_mark("needs_human")[0] == "✗"
    assert status_mark("budget_exhausted")[0] == "⛔"


def test_format_gates_marks_failures():
    text = format_gates({"pytest -q": 0, "ruff check .": 1})
    plain = text.plain
    assert "✓ pytest -q 0" in plain
    assert "✗ ruff check . 1" in plain


def test_format_metrics_shows_budget_and_cost():
    payload = {
        "usage": {
            "total_tokens": 15_000,
            "cost_usd": 0.0,
            "duration_seconds": 125,
            "llm_calls": 7,
        }
    }
    text = format_metrics(payload, models=[("planner", "nvidia/x:free")], fallback=False).plain
    assert "15.0k" in text
    assert "$0" in text
    assert "2m05s" in text
    assert "llm calls 7" in text
    assert "fallback" not in text


def test_format_metrics_marks_unknown_cost_and_fallback():
    text = format_metrics(
        {"usage": {"cost_usd": None}},
        models=[("senior", "glm-5.3-flash")],
        fallback=True,
    ).plain
    assert "unknown" in text
    assert "fallback  ON" in text.replace("  ", "  ")


def test_queue_marks_uses_newest_run_per_task():
    runs = [
        {"spec": "001-example-app", "task": "T1", "status": "needs_human"},
        {"spec": "001-example-app", "task": "T1", "status": "green"},
        {"spec": "001-example-app", "task": "T2", "status": "green"},
        {"spec": "004-weather-sun", "task": "T9", "status": "green"},
    ]
    assert queue_marks(runs, "001-example-app") == {"T1": "needs_human", "T2": "green"}
    assert queue_marks(runs, "001") == {"T1": "needs_human", "T2": "green"}


def test_scan_runs_reads_newest_first_and_skips_junk(tmp_path):
    runs = tmp_path / "swarm" / "runs"
    older = runs / "20260101-000000-1-aaaa"
    newer = runs / "20260102-000000-2-bbbb"
    junk = runs / "plans"
    older.mkdir(parents=True)
    newer.mkdir()
    junk.mkdir()
    (older / "run.json").write_text(json.dumps({"spec": "001", "task": "T1", "status": "green"}))
    (newer / "meta.json").write_text(json.dumps({"spec": "001", "task": "T2"}))
    recs = scan_runs(tmp_path)
    assert [r["task"] for r in recs] == ["T2", "T1"]
    assert recs[0]["run"].startswith("20260102")


def test_format_recent_filters_spec_and_dedupes():
    runs = [
        {"spec": "001-example-app", "task": "T2", "status": "green", "usage": {"total_tokens": 2000}},
        {"spec": "001-example-app", "task": "T2", "status": "needs_human"},
        {"spec": "001-example-app", "task": "T1", "status": "green"},
        {"spec": "004-weather", "task": "T1", "status": "green"},
    ]
    plain = format_recent(runs, "001-example-app").plain
    assert "T2" in plain and "T1" in plain
    assert "T2" in plain.split("T1")[0]  # newest first
    assert "T1" in plain and plain.count("✓ T2") == 1


def test_short_model_hides_provider_prefix():
    from swarm.tui import short_model

    assert short_model("openrouter/nvidia/nemotron-3.5-super-vl:free") == "nemotron-3.5-super-vl:free"
    assert short_model("ollama/swarm-coder:latest") == "swarm-coder:latest"
    assert short_model("zen/glm-5.3-flash") == "glm-5.3-flash"


def test_elapsed_seconds_uses_recorded_then_started_at(tmp_path):
    import time

    from swarm.tui import elapsed_seconds

    assert elapsed_seconds({"usage": {"duration_seconds": 92.4}}) == 92.4
    started = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 10))
    approx = elapsed_seconds({"usage": {"started_at": started}})
    assert approx is not None and 9 <= approx <= 12
    assert elapsed_seconds({}, None) is None


def test_event_error_prefers_message_over_repr():
    import types

    from swarm.events import _event_error

    assert _event_error(types.SimpleNamespace(error="429 rate limit")) == "429 rate limit"
    assert _event_error(types.SimpleNamespace(reason="gate red")) == "gate red"

    class Noisy:
        def __str__(self):
            return "timestamp=datetime.datetime(...) other=1"

    assert _event_error(Noisy()) == "Noisy"


def test_human_report_explains_needs_human():
    from swarm.tui import format_human_report

    payload = {
        "spec": "001-example-app",
        "task": "T10",
        "status": "needs_human",
        "review_verdict": "blocked",
        "gates": {"pytest -q": 0, "npm --prefix frontend run check": 1},
        "review_tail": "svelte-check found 15 errors: Property 'duration_s' does not exist",
        "gate_transcript_tail": "$ npm --prefix frontend run check\nexit=1",
        "changed_files": ["frontend/src/App.svelte"],
    }
    events = [{"type": "task_done", "text": "verdict BLOCKED: TypeScript errors"}]
    text = format_human_report(payload, events, run_name="run-1")
    assert "001-example-app T10 — needs_human" in text
    assert "reviewer verdict: blocked" in text
    assert "svelte-check found 15 errors" in text
    assert "✗ npm --prefix frontend run check 1" in text
    assert "frontend/src/App.svelte" in text
    assert "BLOCKED: TypeScript errors" in text


def test_human_report_for_green_is_short_and_clear():
    from swarm.tui import format_human_report

    text = format_human_report(
        {"spec": "001", "task": "T1", "status": "green", "review_verdict": "pass"},
        [],
    )
    assert "all gates 0 + reviewer PASS + committed" in text
