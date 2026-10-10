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


def test_senior_llm_uses_configured_model(monkeypatch):
    from swarm.llms import senior_llm

    monkeypatch.setenv("SWARM_SENIOR_MODEL", "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free")
    llm = senior_llm()
    assert llm.model == "nvidia/nemotron-3-ultra-550b-a55b:free"  # provider prefix routed off
    assert llm.additional_params.get("extra_body") is None


def test_senior_llm_requires_env(monkeypatch):
    import pytest

    from swarm.llms import senior_llm

    monkeypatch.delenv("SWARM_SENIOR_MODEL", raising=False)
    with pytest.raises(RuntimeError):
        senior_llm()


def test_build_senior_crew_structure():
    from swarm.crew import build_senior_crew
    from swarm.spec_loader import SpecTask

    task = SpecTask(id="T2", ac_refs=("AC-1",), brief="do things")
    crew = build_senior_crew("001", task, "pytest exit=1")
    assert [a.role for a in crew.agents] == ["Senior Developer", "QA Gatekeeper"]
    assert len(crew.tasks) == 2
    assert len(crew.agents[0].tools) >= 4


def test_spec_after_order_and_skips(tmp_path):
    from swarm.flow import _spec_after

    specs = tmp_path / "specs"
    for name, has_tasks in [("001-a", True), ("004-b", True), ("007-c", False), ("009-swarm-harness", True)]:
        d = specs / name
        d.mkdir(parents=True)
        if has_tasks:
            (d / "tasks.md").write_text("x")
    assert _spec_after(tmp_path, "001-a") == "004-b"
    assert _spec_after(tmp_path, "004-b") is None  # 007-c has no tasks, harness excluded
    assert _spec_after(tmp_path, "zzz") is None
