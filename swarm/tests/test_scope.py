from swarm.tools_guarded import DEFAULT_SCOPE, scope_violations


def test_scope_allows_scaffold_paths():
    ok = ["app/main.py", "frontend/x.ts", "contracts/route.json", "requirements-dev.txt", "pyproject.toml"]
    assert scope_violations(ok, DEFAULT_SCOPE) == []


def test_scope_flags_harness_and_docs():
    bad = scope_violations(["swarm/crew.py", "docs/x.md", "app/main.py"], DEFAULT_SCOPE)
    assert bad == ["swarm/crew.py", "docs/x.md"]
