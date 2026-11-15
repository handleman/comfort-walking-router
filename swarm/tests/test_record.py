"""`make swarm-record` writes the standard trailers for manual work (026 AC-10).

A task finished by hand leaves a `- [ ]` line with no trailer, so the queue
re-runs it and nothing says why. The command is an *empty* commit with exactly
the green path's trailers: it must never touch the tree and never edit `specs/`.
"""

from __future__ import annotations

import subprocess

from swarm import record as record_mod
from swarm.done import done_entries, is_done, spec_plan_hash, task_hash
from swarm.spec_loader import load_spec_tasks


def _git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )


def _repo(tmp_path, *, ticked: bool = False):
    repo = tmp_path / "repo"
    spec = repo / "specs" / "014-walking-guide"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text("# spec\n")
    (spec / "plan.md").write_text("# plan\n")
    box = "x" if ticked else " "
    (spec / "tasks.md").write_text(
        f"- [{box}] T1 (AC-1): first thing\n- [ ] T2 (AC-2): second thing\n"
    )
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "swarm@test.local")
    _git(repo, "config", "user.name", "swarm test")
    (repo / ".gitignore").write_text("swarm/runs/\n")
    (repo / "README.md").write_text("# repo\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo, spec


def _patch_root(monkeypatch, repo):
    monkeypatch.setattr(record_mod, "REPO_ROOT", repo)


def test_the_message_carries_the_standard_trailers():
    body = record_mod.message("014-walking-guide", "T11", "a" * 64, "b" * 64, "20260101-000000")
    assert "Swarm-Task: 014-walking-guide/T11" in body
    assert f"Swarm-Task-Hash: {'a' * 64}" in body
    assert f"Swarm-Spec-Hash: {'b' * 64}" in body
    assert "Swarm-Run: manual-20260101-000000" in body
    assert body.startswith("swarm: 014-walking-guide-T11 recorded manually")


def test_record_commits_an_empty_commit_and_the_ledger_agrees(tmp_path, monkeypatch):
    repo, spec = _repo(tmp_path)
    _patch_root(monkeypatch, repo)
    tree_before = _git(repo, "status", "--porcelain").stdout

    assert record_mod.record("014", "T2") == 0

    # The trailering commit carries no file change.
    files = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.strip()
    assert files == ""
    assert _git(repo, "status", "--porcelain").stdout == tree_before

    entries = done_entries(repo)
    _, tasks = load_spec_tasks(repo, "014-walking-guide", None)
    task = next(t for t in tasks if t.id == "T2")
    assert is_done(entries, "014-walking-guide", task, spec_plan_hash(spec))


def test_record_accepts_a_ticked_task(tmp_path, monkeypatch):
    """A manual completion is normally already `- [x]` in tasks.md."""
    repo, _spec = _repo(tmp_path, ticked=True)
    _patch_root(monkeypatch, repo)
    assert record_mod.record("014", "T1") == 0
    entries = done_entries(repo)
    _, tasks = load_spec_tasks(repo, "014-walking-guide", None, include_done=True)
    task = next(t for t in tasks if t.id == "T1")
    assert is_done(entries, "014-walking-guide", task, spec_plan_hash(_spec))


def test_an_unknown_task_is_refused(tmp_path, monkeypatch, capsys):
    repo, _spec = _repo(tmp_path)
    _patch_root(monkeypatch, repo)
    assert record_mod.record("014", "T9") == 2
    assert "no task T9" in capsys.readouterr().out


def test_dry_run_changes_nothing(tmp_path, monkeypatch, capsys):
    repo, _spec = _repo(tmp_path)
    _patch_root(monkeypatch, repo)
    head = _git(repo, "rev-parse", "HEAD").stdout
    assert record_mod.record("014", "T2", dry_run=True) == 0
    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert not (repo / "swarm" / "runs" / "done.json").exists()
    assert "would commit" in capsys.readouterr().out


def test_no_commit_updates_only_the_cache(tmp_path, monkeypatch):
    repo, _spec = _repo(tmp_path)
    _patch_root(monkeypatch, repo)
    head = _git(repo, "rev-parse", "HEAD").stdout
    assert record_mod.record("014", "T2", commit=False) == 0
    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert "014-walking-guide/T2" in done_entries(repo)


def test_the_hash_matches_what_the_queue_would_compute(tmp_path, monkeypatch):
    """A record that hashed differently would be reopened immediately."""
    repo, spec = _repo(tmp_path)
    _patch_root(monkeypatch, repo)
    record_mod.record("014", "T2")
    _, tasks = load_spec_tasks(repo, "014-walking-guide", None)
    task = next(t for t in tasks if t.id == "T2")
    entry = done_entries(repo)["014-walking-guide/T2"]
    assert entry.task_hash == task_hash(task)
    assert entry.spec_hash == spec_plan_hash(spec)
