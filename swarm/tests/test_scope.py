from swarm.tools_guarded import DEFAULT_SCOPE, in_scope, scope_violations


def test_scope_allows_scaffold_paths():
    ok = ["app/main.py", "frontend/x.ts", "tests/test_x.py", "contracts/route.json", "requirements-dev.txt", "pyproject.toml"]
    assert scope_violations(ok, DEFAULT_SCOPE) == []


def test_scope_flags_harness_and_docs():
    bad = ["swarm/crew.py", "docs/x.md", "app/main.py"]
    assert scope_violations(bad, DEFAULT_SCOPE) == ["swarm/crew.py", "docs/x.md"]


def test_scope_exact_files_do_not_prefix_match():
    assert in_scope("pyproject.toml", DEFAULT_SCOPE)
    assert not in_scope("pyproject.toml.bak", DEFAULT_SCOPE)
    assert not in_scope("application/x.py", DEFAULT_SCOPE)


def test_scope_always_blocks_secrets_and_escapes():
    for path in (".env", "app/.env.local", "app/key.pem", "../x.py", "/etc/passwd"):
        assert not in_scope(path, DEFAULT_SCOPE), path
        assert scope_violations([path], DEFAULT_SCOPE) == [path]


def test_scope_rule_matches_default_scope():
    from swarm.crew import SCOPE_RULE

    for entry in DEFAULT_SCOPE:
        assert entry in SCOPE_RULE, entry
    assert "tests/" in SCOPE_RULE


# ---- 022: operator edits are archived, not deleted, and never poison scope ----

def test_out_of_scope_writes_are_archived_before_reverting(tmp_path, monkeypatch):
    import subprocess
    import types

    from swarm import flow

    repo = tmp_path / "repo"
    (repo / "swarm").mkdir(parents=True)
    (repo / "swarm" / "evil.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    monkeypatch.setattr(flow, "REPO_ROOT", repo)
    run_dir = tmp_path / "run"
    stub = types.SimpleNamespace(
        run_dir=run_dir,
        state=types.SimpleNamespace(reverted_archive=[]),
    )
    stub._revert_out_of_scope = types.MethodType(flow.SwarmFlow._revert_out_of_scope, stub)

    assert stub._revert_out_of_scope(["swarm/evil.py"]) == ["swarm/evil.py"]
    assert not (repo / "swarm" / "evil.py").exists()
    archived = run_dir / "reverted" / "swarm" / "evil.py"
    assert archived.read_text() == "x = 1\n"
    assert stub.state.reverted_archive == ["reverted/swarm/evil.py"]


def test_the_gates_revert_operator_edits_before_scoring_scope():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "self._revert_out_of_scope(run_delta(self._baseline))" in source
    assert '"reverted_archive": self.state.reverted_archive' in source


# ---- S1: a docs task must be able to write its own deliverable ----

def test_task_scope_adds_the_brief_paths_outside_the_default_scope():
    from swarm.tools_guarded import DEFAULT_SCOPE, in_scope, task_scope

    brief = (
        "Create `docs/architecture/adr-013-geocoding.md`, update `README.md` "
        "and `docs/roadmap.md`."
    )
    scope = task_scope(DEFAULT_SCOPE, brief)
    assert in_scope("docs/architecture/adr-013-geocoding.md", scope)
    assert in_scope("README.md", scope)
    assert in_scope("docs/roadmap.md", scope)
    # The default code scope is unchanged.
    assert in_scope("app/main.py", scope)
    assert not in_scope("secrets/prod.env", scope)


def test_task_scope_does_not_duplicate_paths_already_in_scope():
    from swarm.tools_guarded import DEFAULT_SCOPE, task_scope

    scope = task_scope(DEFAULT_SCOPE, "Edit `app/main.py`.")
    assert scope == DEFAULT_SCOPE


def test_the_flow_widens_scope_from_the_brief():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert "task_scope(base, tasks[0].brief)" in source
    assert 'os.environ["SWARM_SCOPE"] = ",".join(widened)' in source
