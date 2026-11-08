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
