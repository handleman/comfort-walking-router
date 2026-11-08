import json

import swarm.tools_guarded as tg
from swarm import flow
from swarm.flow import approve_held_run
from swarm.tools_guarded import hash_paths


def _setup(tmp_path, monkeypatch, *, delta=("app/x.py",), status="awaiting_approval"):
    repo = tmp_path / "repo"
    spec = repo / "specs" / "001-x"
    (repo / "app").mkdir(parents=True)
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text("spec")
    (spec / "plan.md").write_text("plan")
    (spec / "tasks.md").write_text("- [ ] T1 (AC-1): do x\n")
    (repo / "app" / "x.py").write_text("print('x')\n")

    monkeypatch.setattr(flow, "REPO_ROOT", repo)
    monkeypatch.setattr(tg, "REPO_ROOT", repo)
    monkeypatch.setattr(tg, "_git_changed", lambda: list(delta))

    run = repo / "swarm" / "runs" / "20260101-000000-1-aaaa"
    run.mkdir(parents=True)
    (run.parent / "latest").write_text(run.name)
    rec = {
        "spec": "001-x",
        "task": "T1",
        "status": status,
        "delta_hashes": hash_paths(list(delta)),
        "head": "",
    }
    (run / "run.json").write_text(json.dumps(rec))
    return repo, run


def _fake_commit(calls):
    def commit(spec, task, brief, paths=None, **kwargs):
        calls.append({"spec": spec, "task": task, "paths": paths, **kwargs})
        return {"ok": "1", "commit": "ok", "push": "ok", "merge": "ok", "branch": f"swarm/{spec}-{task}"}

    return commit


def test_approve_commits_exact_held_delta(tmp_path, monkeypatch):
    repo, run = _setup(tmp_path, monkeypatch)
    calls = []
    result = approve_held_run(repo, "001", "T1", commit_fn=_fake_commit(calls))
    assert result["ok"] == "1"
    assert calls and calls[0]["paths"] == ["app/x.py"]
    assert calls[0]["run_id"] == run.name
    rec = json.loads((run / "run.json").read_text())
    assert rec["status"] == "green"
    assert rec["approved"] is True
    assert rec["approval"]["mode"] == "resume"
    assert rec["done"]["recorded"] is True
    assert (repo / "swarm" / "runs" / "approvals" / "001-x-T1.json").is_file()


def test_approve_refuses_worktree_drift(tmp_path, monkeypatch):
    repo, run = _setup(tmp_path, monkeypatch)
    (repo / "app" / "x.py").write_text("changed\n")
    result = approve_held_run(repo, "001", "T1", commit_fn=_fake_commit([]))
    assert result["ok"] == "0"
    assert "worktree changed" in result["note"]
    assert json.loads((run / "run.json").read_text())["status"] == "awaiting_approval"


def test_approve_refuses_new_in_scope_changes(tmp_path, monkeypatch):
    repo, _run = _setup(tmp_path, monkeypatch)
    (repo / "app" / "y.py").write_text("extra\n")
    monkeypatch.setattr(tg, "_git_changed", lambda: ["app/x.py", "app/y.py"])
    result = approve_held_run(repo, "001", "T1", commit_fn=_fake_commit([]))
    assert result["ok"] == "0"
    assert "new in-scope changes" in result["note"]


def test_approve_ignores_out_of_scope_drift(tmp_path, monkeypatch):
    repo, _run = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(tg, "_git_changed", lambda: ["app/x.py", "docs/notes.md"])
    result = approve_held_run(repo, "001", "T1", commit_fn=_fake_commit([]))
    assert result["ok"] == "1"


def test_approve_requires_a_held_run(tmp_path, monkeypatch):
    repo, _run = _setup(tmp_path, monkeypatch, status="green")
    result = approve_held_run(repo, "001", "T1", commit_fn=_fake_commit([]))
    assert result["ok"] == "0"
    assert result["code"] == "none"


def test_approve_commit_failure_keeps_run_held(tmp_path, monkeypatch):
    repo, run = _setup(tmp_path, monkeypatch)

    def failing(spec, task, brief, paths=None, **kwargs):
        return {"ok": "0", "merge": "conflict: boom"}

    result = approve_held_run(repo, "001", "T1", commit_fn=failing)
    assert result["ok"] == "0"
    rec = json.loads((run / "run.json").read_text())
    assert rec["status"] == "awaiting_approval"
    assert "conflict" in rec["approval_error"]
