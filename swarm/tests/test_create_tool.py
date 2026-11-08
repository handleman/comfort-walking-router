from swarm.tools_guarded import CreateTool


def test_create_new_file_with_parents(tmp_path, monkeypatch):
    import swarm.tools_guarded as tg

    monkeypatch.setattr(tg, "REPO_ROOT", tmp_path)
    out = CreateTool()._run(path="app/__init__.py", content="")
    assert out.startswith("OK")
    assert (tmp_path / "app" / "__init__.py").is_file()


def test_create_refuses_existing_and_escape(tmp_path, monkeypatch):
    import swarm.tools_guarded as tg

    monkeypatch.setattr(tg, "REPO_ROOT", tmp_path)
    f = tmp_path / "x.txt"
    f.write_text("hi")
    assert CreateTool()._run(path="x.txt").startswith("BLOCKED")
    assert CreateTool()._run(path="../escape.txt").startswith("BLOCKED")
    assert CreateTool()._run(path="/tmp/escape.txt").startswith("BLOCKED")


def test_create_refuses_out_of_scope_and_secret_paths(tmp_path, monkeypatch):
    import swarm.tools_guarded as tg

    monkeypatch.setattr(tg, "REPO_ROOT", tmp_path)
    assert "outside coder scope" in CreateTool()._run(path="swarm/evil.py")
    assert CreateTool()._run(path=".env").startswith("BLOCKED")
    assert CreateTool()._run(path="app/.env").startswith("BLOCKED")
