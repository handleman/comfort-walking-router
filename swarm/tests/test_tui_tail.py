import json

from swarm.tui import SwarmTUI


def _app(run_dir):
    app = SwarmTUI("001", "T1", tail=str(run_dir))
    app._plan_noted = True
    seen: list[str] = []
    app._pane_log = lambda pane, text: seen.append(text)  # type: ignore[method-assign]
    app._set_status = lambda text: None  # type: ignore[method-assign]
    return app, seen


def test_tail_is_incremental_and_deduplicated(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    events = run / "events.jsonl"
    events.write_text('{"type":"crew_done"}\n')
    app, seen = _app(run)

    app._poll_tail()
    assert len(seen) == 1
    app._poll_tail()
    assert len(seen) == 1  # offset advanced: no re-read

    with events.open("a") as f:
        f.write('{"type":"task_done"}\n{"type":"crew_done"}\n')
    app._poll_tail()
    assert len(seen) == 3


def test_tail_waits_for_complete_lines(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    events = run / "events.jsonl"
    events.write_text('{"type":"crew_')
    app, seen = _app(run)

    app._poll_tail()
    assert seen == []  # partial line stays buffered

    with events.open("a") as f:
        f.write('done"}\n')
    app._poll_tail()
    assert len(seen) == 1


def test_tail_follows_run_switch_and_resets_offset(tmp_path, monkeypatch):
    first = tmp_path / "swarm" / "runs" / "20260101-000000-1-aaaa"
    second = tmp_path / "swarm" / "runs" / "20260101-000001-2-bbbb"
    first.mkdir(parents=True)
    second.mkdir()
    (first / "events.jsonl").write_text('{"type":"crew_done"}\n')
    (second / "events.jsonl").write_text('{"type":"task_done"}\n{"type":"crew_done"}\n')
    (second / "meta.json").write_text(json.dumps({"spec": "001-x", "task": "T2"}))
    (tmp_path / "swarm" / "runs" / "latest").write_text(second.name)

    from swarm import tui

    monkeypatch.setattr(tui, "REPO_ROOT", tmp_path)
    app, seen = _app(first)
    app._poll_tail()
    assert app._run_dir == second
    assert "task done" in seen and "crew done" in seen
    assert any("following" in s for s in seen)


def test_run_dirs_and_shift(tmp_path):
    from swarm.tui import run_dirs, shift_run

    runs = tmp_path / "swarm" / "runs"
    older = runs / "20260101-000000-1-aaaa"
    newer = runs / "20260102-000000-2-bbbb"
    older.mkdir(parents=True)
    newer.mkdir()
    (runs / "plans").mkdir()
    (runs / "latest").write_text(newer.name)
    dirs = run_dirs(tmp_path)
    assert dirs == [newer, older]
    assert shift_run(dirs, newer, -1) == older
    assert shift_run(dirs, older, -1) is None
    assert shift_run(dirs, older, 1) == newer
    assert shift_run(dirs, newer, 1) is None
    assert shift_run([], newer, 1) is None


def _fresh_app(run_dir):
    app = SwarmTUI("001-x", "T1", tail=str(run_dir))
    app._plan_noted = True
    seen: list[str] = []
    app._pane_log = lambda pane, text: seen.append(text)  # type: ignore[method-assign]
    app._set_status = lambda text: None  # type: ignore[method-assign]
    app._clear_logs = lambda: None  # type: ignore[method-assign]
    return app, seen


def test_fresh_attach_skips_prior_events(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    events = run / "events.jsonl"
    events.write_text('{"type":"crew_done"}\n{"type":"task_done"}\n')
    app, seen = _fresh_app(run)

    app._seek_end()
    assert app._tail_pos == events.stat().st_size
    app._poll_tail()
    assert seen == []  # nothing from before this session


def test_history_key_replays_and_hides_events(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "events.jsonl").write_text('{"type":"crew_done"}\n{"type":"task_done"}\n')
    app, seen = _fresh_app(run)

    app.action_history()
    assert app._history_open is True
    assert any("history:" in s for s in seen)
    assert "task done" in seen
    assert app._tail_pos == (run / "events.jsonl").stat().st_size

    app.action_history()
    assert app._history_open is False
    assert seen[-1].startswith("history hidden")


def test_new_events_after_fresh_attach_are_shown(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    events = run / "events.jsonl"
    events.write_text('{"type":"crew_done"}\n')
    app, seen = _fresh_app(run)
    app._seek_end()

    with events.open("a") as f:
        f.write('{"type":"task_done"}\n')
    app._poll_tail()
    assert "task done" in seen
