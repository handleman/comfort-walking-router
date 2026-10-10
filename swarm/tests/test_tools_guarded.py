from swarm.tools_guarded import EditTool, ShellTool


def test_shell_blocks_non_allowlisted():
    out = ShellTool()._run("rm -rf /tmp/x")
    assert out.startswith("BLOCKED")


def test_shell_blocks_writes_and_network():
    for cmd in ("python -c '1'", "sed -i s/a/b/ f", "curl http://x", "pip install y"):
        assert ShellTool()._run(cmd).startswith("BLOCKED"), cmd


def test_shell_allows_extended_readonly():
    for cmd in ("git status --short", "grep -n once README.md", "ls README.md"):
        assert ShellTool()._run(cmd).startswith("exit="), cmd


def test_shell_allows_ls():
    out = ShellTool()._run("ls README.md")
    assert "exit=0" in out


def test_edit_requires_exact_single_match(tmp_path, monkeypatch):
    import swarm.tools_guarded as tg

    f = tmp_path / "a.txt"
    f.write_text("x x x")
    monkeypatch.setattr(tg, "REPO_ROOT", tmp_path)
    out = EditTool()._run(path="a.txt", oldString="x", newString="y")
    assert "exactly 1" in out
    out2 = EditTool()._run(path="../escape.txt", oldString="a", newString="b")
    assert out2.startswith("BLOCKED")
