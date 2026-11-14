"""Delta guard tests (026 AC-1/AC-2): stop before a judge is paid."""

from __future__ import annotations

from pathlib import Path

from swarm import guards


def test_an_empty_delta_is_no_delta(tmp_path: Path):
    record = guards.delta_record("Edit `app/main.py`.", [], tmp_path)
    assert record["reason"] == "no_delta"
    assert record["changed"] == []
    assert "no in-scope change" in guards.summary(record)


def test_a_named_file_that_was_never_created_is_incomplete(tmp_path: Path):
    (tmp_path / "README.md").write_text("# x\n")  # exists, untouched
    brief = "Create `docs/architecture/adr-013-geocoding.md` and update `README.md`."
    record = guards.delta_record(brief, ["frontend/src/App.svelte"], tmp_path)
    assert record["reason"] == "delta_incomplete"
    assert record["missing"] == ["docs/architecture/adr-013-geocoding.md"]
    assert record["untouched"] == ["README.md"]
    assert "adr-013-geocoding.md" in guards.summary(record)


def test_a_named_existing_file_untouched_is_only_a_warning(tmp_path: Path):
    (tmp_path / "README.md").write_text("# x\n")
    record = guards.delta_record("Update `README.md`.", ["app/main.py"], tmp_path)
    assert record["reason"] == ""
    assert record["untouched"] == ["README.md"]
    assert "named but untouched" in guards.summary(record)


def test_a_complete_delta_passes(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("x = 1\n")
    record = guards.delta_record("Edit `app/main.py`.", ["app/main.py"], tmp_path)
    assert record["reason"] == ""
    assert record["missing"] == [] and record["untouched"] == []


def test_the_guard_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SWARM_DELTA_GUARD", "0")
    assert guards.enabled() is False
    monkeypatch.setenv("SWARM_DELTA_GUARD", "1")
    assert guards.enabled() is True


def test_the_guard_runs_before_the_self_check_and_the_verifier():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    guard = source.index("raise _DeltaStop")
    self_check = source.index("self._self_check_phase(")
    verifier = source.index("self._verify_phase(task, _verify_kick)")
    assert guard < self_check < verifier


def test_the_reason_code_is_machine_readable():
    import types

    from swarm.flow import _reason_code

    state = types.SimpleNamespace(delta_guard={"reason": "no_delta"}, verifier={})
    assert _reason_code("needs_human", {}, state) == "no_delta"
    state.delta_guard = {"reason": "delta_incomplete"}
    assert _reason_code("needs_human", {}, state) == "delta_incomplete"
