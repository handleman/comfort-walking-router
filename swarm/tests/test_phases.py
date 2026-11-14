"""Phase timing tests (022 T1): attribution from the event stream only."""

from __future__ import annotations

from pathlib import Path

from swarm import phases


def _ev(kind: str, at: str, role: str = "", **extra) -> dict:
    return {"type": kind, "at": at, "role": role, **extra}


def test_derive_pairs_crew_events_and_computes_durations():
    events = [
        _ev("crew_started", "2026-11-14T10:00:00.000", "planner", model="m1"),
        _ev("crew_done", "2026-11-14T10:00:30.500", "planner"),
        _ev("crew_started", "2026-11-14T10:00:31.000", "coder:step1"),
        _ev("crew_done", "2026-11-14T10:01:11.000", "coder:step1"),
    ]
    out = phases.derive(events)
    assert [p["phase"] for p in out] == ["planner", "coder:step1"]
    assert out[0]["duration_seconds"] == 30.5
    assert out[1]["duration_seconds"] == 40.0
    assert out[0]["failed"] is False


def test_a_failed_crew_is_a_phase_not_a_gap():
    events = [
        _ev("crew_started", "2026-11-14T10:00:00.000", "qa"),
        _ev("crew_failed", "2026-11-14T10:02:00.000", "qa"),
    ]
    out = phases.derive(events)
    assert out[0]["phase"] == "qa" and out[0]["failed"] is True
    assert out[0]["duration_seconds"] == 120.0


def test_nesting_uses_a_stack():
    events = [
        _ev("crew_started", "2026-11-14T10:00:00.000", "outer"),
        _ev("crew_started", "2026-11-14T10:00:05.000", "inner"),
        _ev("crew_done", "2026-11-14T10:00:10.000", "inner"),
        _ev("crew_done", "2026-11-14T10:00:20.000", "outer"),
    ]
    out = phases.derive(events)
    assert [(p["phase"], p["duration_seconds"]) for p in out] == [("inner", 5.0), ("outer", 20.0)]


def test_malformed_timestamps_do_not_crash():
    events = [
        _ev("crew_started", "not-a-time", "x"),
        _ev("crew_done", "2026-11-14T10:00:00.000", "x"),
        _ev("crew_done", "2026-11-14T10:00:01.000", "orphan"),
    ]
    out = phases.derive(events)
    assert out[0]["duration_seconds"] == 0.0


def test_totals_name_the_slowest_phase():
    out = [
        {"phase": "planner", "duration_seconds": 10.0},
        {"phase": "qa", "duration_seconds": 90.0},
    ]
    total = phases.totals(out)
    assert total["total_seconds"] == 100.0
    assert total["slowest_phase"] == "qa" and total["slowest_seconds"] == 90.0


def test_the_listener_tags_events_with_the_current_role(tmp_path: Path):
    from swarm.events import SwarmListener

    listener = SwarmListener(tmp_path)
    listener.current_role = "coder:step2"
    listener._append({"type": "crew_started"})
    listener.current_role = ""
    listener._append({"type": "crew_done"})
    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert '"role": "coder:step2"' in lines[0]
    assert '"role"' not in lines[1]
    listener.teardown()


def test_run_json_records_phases_and_report_aggregates_them():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert '"phases": _phase_records(self.run_dir)' in source

    from swarm import report

    rows = [
        {"status": "green", "fix_rounds": 0, "usage": {"duration_seconds": 100},
         "phases": [{"phase": "planner", "duration_seconds": 10}, {"phase": "qa", "duration_seconds": 30}]},
        {"status": "green", "fix_rounds": 0, "usage": {"duration_seconds": 120},
         "phases": [{"phase": "planner", "duration_seconds": 20}, {"phase": "qa", "duration_seconds": 50}]},
    ]
    summary = report.summarize(rows)
    assert summary["phases"]["planner"]["p50"] == 15.0
    assert summary["phases"]["qa"]["p50"] == 40.0
    text = report.render(summary)
    assert "phases (p50/p90, seconds):" in text
    assert "planner" in text and "qa" in text


# ---- 022 review fixes: concurrency-safe attribution ----


def test_out_of_order_completion_pairs_by_role():
    events = [
        _ev("crew_started", "2026-11-14T10:00:00.000", "verifier"),
        _ev("crew_started", "2026-11-14T10:00:01.000", "qa"),
        _ev("crew_done", "2026-11-14T10:00:30.000", "verifier"),
        _ev("crew_done", "2026-11-14T10:00:21.000", "qa"),
    ]
    out = {p["phase"]: p["duration_seconds"] for p in phases.derive(events)}
    assert out == {"verifier": 30.0, "qa": 20.0}


def test_the_listener_role_is_thread_local(tmp_path: Path):
    import threading

    from swarm.events import SwarmListener

    listener = SwarmListener(tmp_path)
    barrier = threading.Barrier(2)

    def worker(role: str) -> None:
        listener.current_role = role
        barrier.wait()
        listener._append({"type": "crew_started"})
        listener.current_role = ""

    threads = [threading.Thread(target=worker, args=(role,)) for role in ("verifier", "qa")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    listener.teardown()
    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert any('"role": "verifier"' in line for line in lines)
    assert any('"role": "qa"' in line for line in lines)


def test_usage_attribution_uses_the_crew_own_tokens_not_a_shared_diff():
    import types

    from swarm.flow import SwarmFlow

    class Out:
        token_usage = types.SimpleNamespace(
            prompt_tokens=10, completion_tokens=2, cached_prompt_tokens=1,
            total_tokens=12, successful_requests=1,
        )

    class Crew:
        agents = ()
        usage_metrics = None

    stub = types.SimpleNamespace(
        state=types.SimpleNamespace(
            prompt_tokens=1000, completion_tokens=100, cached_prompt_tokens=0,
            total_tokens=1100, llm_calls=5, models_used=[],
        ),
        _usage_by_role={}, _usage_by_step={}, _state_lock=__import__("threading").Lock(),
    )
    stub._record_usage = types.MethodType(SwarmFlow._record_usage, stub)
    SwarmFlow._record_usage(stub, Crew(), Out(), role="verifier", step=None, before=(0, 0))
    assert stub._usage_by_role["verifier"]["prompt_tokens"] == 10
    assert stub.state.prompt_tokens == 1010


# ---- 022 T6 findings: clock jumps and CrewAI's cross-thread events ----


def test_monotonic_stamps_win_over_a_wall_clock_jump():
    events = [
        {"type": "crew_started", "at": "2026-11-14T08:23:00.000", "mono": 10.0, "role": "qa"},
        {"type": "crew_done", "at": "2026-11-14T09:19:00.000", "mono": 40.0, "role": "qa"},
    ]
    out = phases.derive(events)
    assert out[0]["duration_seconds"] == 30.0  # not the 56-minute clock jump


def test_a_crew_object_maps_to_the_role_the_flow_started():
    import types

    from swarm.events import SwarmListener

    listener = SwarmListener.__new__(SwarmListener)  # no bus registration needed
    listener._crew_roles = {}
    listener._role_local = __import__("threading").local()
    crew = types.SimpleNamespace()
    listener.register_crew(crew, "verifier:1")
    event = types.SimpleNamespace(crew=crew)
    assert listener.crew_role(event, None) == "verifier:1"
    listener.forget_crew(crew)
    assert listener.crew_role(event, None) == ""


def test_the_listener_stamps_monotonic_time(tmp_path: Path):
    from swarm.events import SwarmListener

    listener = SwarmListener(tmp_path)
    listener._append({"type": "crew_started"})
    listener.teardown()
    line = (tmp_path / "events.jsonl").read_text().strip()
    assert '"mono"' in line
