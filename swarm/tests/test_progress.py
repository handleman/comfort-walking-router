import datetime as dt
import hashlib
import json
import types

import swarm.tools_guarded as tg
from swarm import flow
from swarm.flow import SwarmFlow, load_checkpoint
from swarm.spec_loader import SpecTask
from swarm.tools_guarded import hash_paths


def _repo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "x.py").write_text("print('x')\n")
    monkeypatch.setattr(tg, "REPO_ROOT", repo)
    monkeypatch.setattr(tg, "_git_changed", lambda: ["app/x.py"])
    return repo


def _progress(prev_run, *, plan_hash, steps=("a", "b"), completed=1):
    payload = {
        "run_id": prev_run.name,
        "spec": "001-x",
        "task": "T1",
        "plan_hash": plan_hash,
        "steps": list(steps),
        "completed": completed,
        "step_outputs": [f"--- step {i}/{len(steps)} ---\nok" for i in range(1, completed + 1)],
        "delta_hashes": hash_paths(["app/x.py"]),
        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    (prev_run / "progress.json").write_text(json.dumps(payload))
    return payload


def test_load_checkpoint_accepts_matching_state(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    prev = repo / "swarm" / "runs" / "20260101-000000-1-aaaa"
    prev.mkdir(parents=True)
    prog = _progress(prev, plan_hash="p" * 64)
    got, note = load_checkpoint(
        prev, spec_dir="001-x", task_id="T1", plan_hash="p" * 64, steps=["a", "b"]
    )
    assert note == ""
    assert got == prog


def test_load_checkpoint_rejects_plan_or_file_changes(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    prev = repo / "swarm" / "runs" / "20260101-000000-1-aaaa"
    prev.mkdir(parents=True)
    _progress(prev, plan_hash="p" * 64)

    _, note = load_checkpoint(prev, spec_dir="001-x", task_id="T1", plan_hash="q" * 64, steps=["a", "b"])
    assert note == "plan changed"

    (repo / "app" / "x.py").write_text("changed\n")
    _, note = load_checkpoint(prev, spec_dir="001-x", task_id="T1", plan_hash="p" * 64, steps=["a", "b"])
    assert note == "worktree changed"


def test_load_checkpoint_rejects_old_and_malformed(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    prev = repo / "swarm" / "runs" / "20260101-000000-1-aaaa"
    prev.mkdir(parents=True)
    prog = _progress(prev, plan_hash="p" * 64)
    prog["updated_at"] = "2000-01-01T00:00:00"
    (prev / "progress.json").write_text(json.dumps(prog))
    _, note = load_checkpoint(
        prev, spec_dir="001-x", task_id="T1", plan_hash="p" * 64, steps=["a", "b"], max_age=10
    )
    assert note == "checkpoint too old"

    prog["completed"] = 5
    (prev / "progress.json").write_text(json.dumps(prog))
    _, note = load_checkpoint(prev, spec_dir="001-x", task_id="T1", plan_hash="p" * 64, steps=["a", "b"])
    assert note == "malformed progress"


def test_previous_run_matches_spec_and_task(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    runs = repo / "swarm" / "runs"
    old = runs / "20260101-000000-1-aaaa"
    new = runs / "20260102-000000-2-bbbb"
    current = runs / "20260103-000000-3-cccc"
    for d in (old, new, current):
        d.mkdir(parents=True)
    (old / "meta.json").write_text(json.dumps({"spec": "001-x", "task": "T1"}))
    (new / "meta.json").write_text(json.dumps({"spec": "001-x", "task": "T1"}))
    (current / "meta.json").write_text(json.dumps({"spec": "001-x", "task": "T1"}))
    assert flow._previous_run(repo, "001-x", "T1", current) == new


def test_resume_checkpoint_uses_killed_run_only(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    runs = repo / "swarm" / "runs"
    prev = runs / "20260101-000000-1-aaaa"
    current = runs / "20260102-000000-2-bbbb"
    prev.mkdir(parents=True)
    current.mkdir(parents=True)
    (prev / "meta.json").write_text(json.dumps({"spec": "001-x", "task": "T1"}))
    plan = "STEP 1: app/x.py — a\nSTEP 2: app/x.py — b"
    plan_hash = hashlib.sha256(plan.encode()).hexdigest()
    _progress(prev, plan_hash=plan_hash)

    monkeypatch.setattr(flow, "REPO_ROOT", repo)
    stub = types.SimpleNamespace(
        run_dir=current,
        state=types.SimpleNamespace(spec_dir="001-x", task_id="T1"),
    )
    task = SpecTask(id="T1", ac_refs=("AC-1",), brief="do x")
    prog, note = SwarmFlow._resume_checkpoint(stub, task, plan, ["a", "b"])
    assert note == ""
    assert prog and prog["completed"] == 1

    (prev / "run.json").write_text(json.dumps({"spec": "001-x", "task": "T1", "status": "green"}))
    prog, note = SwarmFlow._resume_checkpoint(stub, task, plan, ["a", "b"])
    assert prog is None and note == ""


def test_write_progress_is_atomic_and_hashes_delta(tmp_path, monkeypatch):
    repo = _repo(tmp_path, monkeypatch)
    run = repo / "swarm" / "runs" / "run-1"
    run.mkdir(parents=True)
    stub = types.SimpleNamespace(
        run_dir=run,
        state=types.SimpleNamespace(spec_dir="001-x", task_id="T1"),
        _baseline={},
    )
    SwarmFlow._write_progress(stub, "p" * 64, ["a", "b"], 1, ["out-1"])
    prog = json.loads((run / "progress.json").read_text())
    assert prog["completed"] == 1
    assert prog["step_outputs"] == ["out-1"]
    assert prog["delta_hashes"] == hash_paths(["app/x.py"])
    assert not (run / "progress.tmp").exists()
