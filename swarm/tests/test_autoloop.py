"""Autonomous loop: next-task order + scope-confined autocommit (no LLM, no git)."""

import subprocess

from swarm.flow import _commit_changes, _next_after


def test_next_after_order():
    assert _next_after(["T1", "T2", "T3"], "T1") == "T2"
    assert _next_after(["T1", "T2", "T3"], "T3") is None
    assert _next_after(["T1", "T2"], "T9") is None


class _FakeProc:
    def __init__(self, rc=0, out="ok"):
        self.returncode = rc
        self.stdout = out
        self.stderr = ""


def _fake_git(monkeypatch, changed, calls):
    monkeypatch.setattr("swarm.tools_guarded._git_changed", lambda: changed)

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", fake_run)


def test_commit_adds_only_scope_files(monkeypatch):
    calls = []
    _fake_git(monkeypatch, ["app/x.py", "swarm/crew.py", "docs/m.md"], calls)
    rec = _commit_changes("001", "T2", "do things")
    assert rec["commit"].startswith("swarm: 001-T2 green")
    assert rec["push"] == "ok"
    add = calls[0]
    assert add[:3] == ["git", "add", "-A"]
    assert "app/x.py" in add
    assert "swarm/crew.py" not in add
    assert "docs/m.md" not in add


def test_commit_clean_when_nothing_changed(monkeypatch):
    calls = []
    _fake_git(monkeypatch, [], calls)
    rec = _commit_changes("001", "T2", "do things")
    assert rec["commit"].startswith("clean")
    assert calls == []


def test_commit_refuses_env_paths(monkeypatch):
    calls = []
    monkeypatch.setenv("SWARM_SCOPE", "app/,.env")
    _fake_git(monkeypatch, [".env", "app/x.py"], calls)
    rec = _commit_changes("001", "T2", "do things")
    assert rec["commit"].startswith("refused")
    assert calls == []
