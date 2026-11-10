from swarm import flow


def _fake_git(*, merge_rc: int = 1, unmerged: str = "frontend/src/App.svelte\n"):
    calls: list[list[str]] = []

    def fake(args, timeout=120):
        calls.append(list(args))
        if args[:2] == ["rev-parse", "--abbrev-ref"]:
            return 0, "main\n"
        if args[:2] == ["rev-parse", "--verify"]:
            return 1, ""  # branch does not exist yet
        if args[:2] == ["merge", "--no-ff"]:
            return merge_rc, ("CONFLICT (content): Merge conflict in frontend/src/App.svelte" if merge_rc else "")
        if args[:3] == ["diff", "--name-only", "--diff-filter=U"]:
            return 0, unmerged
        return 0, ""

    return calls, fake


def test_commit_changes_keeps_a_crew_resolved_merge(monkeypatch):
    calls, fake = _fake_git()
    monkeypatch.setattr(flow, "_git", fake)
    seen: dict[str, list[str]] = {}

    def resolver(files):
        seen["files"] = list(files)
        return True, "crew resolved; gates: 4/4 green"

    rec = flow._commit_changes(
        "016", "T1", "brief", paths=["frontend/src/App.svelte"], resolver=resolver
    )

    assert seen["files"] == ["frontend/src/App.svelte"]
    assert rec["ok"] == "1"
    assert "crew resolved" in rec["merge"]
    assert "gates: 4/4 green" in rec["conflict"]
    assert ["add", "--", "frontend/src/App.svelte"] in calls
    assert ["merge", "--abort"] not in calls


def test_commit_changes_aborts_when_the_crew_fails(monkeypatch):
    calls, fake = _fake_git()
    monkeypatch.setattr(flow, "_git", fake)
    rec = flow._commit_changes(
        "016",
        "T1",
        "brief",
        paths=["frontend/src/App.svelte"],
        resolver=lambda files: (False, "conflict markers left in frontend/src/App.svelte"),
    )

    assert rec["ok"] == "0"
    assert rec["merge"].startswith("conflict:")
    assert "markers left" in rec["conflict"]
    assert ["merge", "--abort"] in calls


def test_commit_changes_without_a_resolver_is_unchanged(monkeypatch):
    calls, fake = _fake_git()
    monkeypatch.setattr(flow, "_git", fake)
    rec = flow._commit_changes("016", "T1", "brief", paths=["frontend/src/App.svelte"])
    assert rec["ok"] == "0"
    assert ["merge", "--abort"] in calls


def test_conflict_markers_finds_leftovers(tmp_path, monkeypatch):
    monkeypatch.setattr(flow, "REPO_ROOT", tmp_path)
    (tmp_path / "ok.ts").write_text("export const x = 1\n")
    (tmp_path / "bad.ts").write_text("<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> swarm\n")
    assert flow.conflict_markers(["ok.ts", "bad.ts", "missing.ts"]) == ["bad.ts", "missing.ts"]


def test_conflict_crew_is_disabled_by_env(monkeypatch):
    monkeypatch.setenv("SWARM_CONFLICT_CREW", "0")
    stub = type("S", (), {})()
    stub.state = flow.SwarmState()
    ok, note = flow.SwarmFlow._resolve_conflict(stub, ["frontend/src/App.svelte"])
    assert ok is False
    assert "disabled" in note


def test_acceptance_requires_markers_gone_and_gates_green(monkeypatch):
    import swarm.crew as crew_mod

    class FakeCrew:
        def __init__(self):
            self.agents = []

        def kickoff(self):
            return object()

    monkeypatch.setattr(crew_mod, "build_conflict_crew", lambda *a, **k: FakeCrew())
    monkeypatch.setattr(flow.SwarmFlow, "_record_usage", lambda *a, **k: None)

    stub = type("S", (), {})()
    stub.state = flow.SwarmState()
    stub.state.spec_dir = "016"
    stub.state.task_id = "T1"
    stub._record_usage = lambda *a, **k: None

    monkeypatch.setattr(flow, "_git", lambda args, timeout=120: (0, "frontend/src/App.svelte\n"))
    monkeypatch.setattr(flow, "conflict_markers", lambda paths: ["frontend/src/App.svelte"])
    assert flow.SwarmFlow._resolve_conflict(stub, ["frontend/src/App.svelte"])[0] is False

    monkeypatch.setattr(flow, "conflict_markers", lambda paths: [])
    monkeypatch.setattr(flow, "_run_gate_commands", lambda: [("pytest -q", 1, "boom")])
    ok, note = flow.SwarmFlow._resolve_conflict(stub, ["frontend/src/App.svelte"])
    assert ok is False and "failed gates" in note

    monkeypatch.setattr(flow, "_run_gate_commands", lambda: [("pytest -q", 0, "")])
    ok, note = flow.SwarmFlow._resolve_conflict(stub, ["frontend/src/App.svelte"])
    assert ok is True and "1/1 green" in note


def test_conflict_crew_has_no_gate_tool(monkeypatch):
    from swarm import crew as crew_mod

    monkeypatch.setenv("SWARM_CONFLICT_MODEL", "ollama/swarm-coder:latest")
    c = crew_mod.build_conflict_crew("016", "T1", ["frontend/src/App.svelte"])
    names = [type(t).__name__ for t in c.agents[0].tools]
    assert "ShellTool" not in names
    assert "EditTool" in names


def test_conflict_llm_defaults_to_the_coder_model(monkeypatch):
    from swarm import llms

    monkeypatch.setenv("SWARM_CODER_MODEL", "ollama/swarm-coder:latest")
    monkeypatch.delenv("SWARM_CONFLICT_MODEL", raising=False)
    assert llms.conflict_llm().model == "ollama/swarm-coder:latest"


def test_resolver_rejects_edits_outside_the_conflicted_files(monkeypatch):
    import swarm.crew as crew_mod

    class FakeCrew:
        def __init__(self):
            self.agents = []

        def kickoff(self):
            return object()

    monkeypatch.setattr(crew_mod, "build_conflict_crew", lambda *a, **k: FakeCrew())
    monkeypatch.setattr(flow.SwarmFlow, "_record_usage", lambda *a, **k: None)
    monkeypatch.setattr(
        flow, "_git", lambda args, timeout=120: (0, "frontend/src/App.svelte\nfrontend/src/other.ts\n")
    )

    stub = type("S", (), {})()
    stub.state = flow.SwarmState()
    stub.state.spec_dir = "016"
    stub.state.task_id = "T1"
    stub._record_usage = lambda *a, **k: None

    ok, note = flow.SwarmFlow._resolve_conflict(stub, ["frontend/src/App.svelte"])
    assert ok is False
    assert "outside the conflict" in note


def test_stash_crew_has_no_gate_tool_and_names_the_stash(monkeypatch):
    from swarm import crew as crew_mod

    monkeypatch.setenv("SWARM_CODER_MODEL", "ollama/swarm-coder:latest")
    c = crew_mod.build_stash_crew(
        "016", "T1", ["frontend/src/App.svelte"], stash="swarm-parked"
    )

    names = [type(t).__name__ for t in c.agents[0].tools]
    assert "ShellTool" not in names
    assert "EditTool" in names
    desc = c.tasks[0].description
    assert "swarm-parked" in desc
    assert "Conflicted files" in desc
    assert "do not duplicate" in desc.lower()
