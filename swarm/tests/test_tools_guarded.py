from swarm.tools_guarded import ALLOWED_COMMANDS, EditTool, ShellTool, _valid_npm


def test_shell_blocks_non_allowlisted():
    out = ShellTool()._run("rm -rf /tmp/x")
    assert out.startswith("BLOCKED")


def test_shell_blocks_writes_and_network():
    for cmd in ("python -c '1'", "sed -i s/a/b/ f", "curl http://x", "pip install y", "uv sync"):
        assert ShellTool()._run(cmd).startswith("BLOCKED"), cmd


def test_shell_blocks_secret_and_escape_reads():
    for cmd in ("cat .env", "cat swarm/.env", "cat /etc/passwd", "cat ../secret", "grep -r token .", "ls /tmp"):
        assert ShellTool()._run(cmd).startswith("BLOCKED"), cmd


def test_shell_blocks_shell_metacharacters():
    for cmd in ("git status; rm -rf /", "git status && echo pwn", "cat README.md | sh", "echo $(whoami)"):
        assert ShellTool()._run(cmd).startswith("BLOCKED"), cmd


def test_shell_blocks_npm_install_and_unprefixed_scripts():
    for cmd in ("npm install", "npm run check", "npm --prefix frontend install"):
        assert ShellTool()._run(cmd).startswith("BLOCKED"), cmd


def test_shell_allows_extended_readonly():
    for cmd in ("git status --short", "grep -n once README.md", "ls README.md", "ruff check README.md"):
        assert ShellTool()._run(cmd).startswith("exit="), cmd


def test_shell_allows_ls():
    out = ShellTool()._run("ls README.md")
    assert "exit=0" in out


def test_npm_validator_allowlist():
    assert _valid_npm(["npm", "--prefix", "frontend", "run", "check"])
    assert _valid_npm(["npm", "--prefix", "frontend", "run", "build"])
    assert _valid_npm(["npm", "--prefix", "frontend", "test", "--", "--run"])
    assert not _valid_npm(["npm", "--prefix", "frontend", "run", "test", "--", "--run", "extra"])
    assert "pip" not in ALLOWED_COMMANDS


def test_edit_requires_exact_single_match(tmp_path, monkeypatch):
    import swarm.tools_guarded as tg

    (tmp_path / "app").mkdir()
    f = tmp_path / "app" / "a.txt"
    f.write_text("x x x")
    monkeypatch.setattr(tg, "REPO_ROOT", tmp_path)
    out = EditTool()._run(path="app/a.txt", oldString="x", newString="y")
    assert "exactly 1" in out
    out2 = EditTool()._run(path="../escape.txt", oldString="a", newString="b")
    assert out2.startswith("BLOCKED")
    out3 = EditTool()._run(path="README.md", oldString="a", newString="b")
    assert out3.startswith("BLOCKED")
    assert "outside coder scope" in out3


def test_configured_gate_commands_are_allowed(monkeypatch):
    monkeypatch.setenv("SWARM_GATE_COMMANDS", "make --version")
    assert ShellTool()._run("make --version").startswith("exit=0")
    assert ShellTool()._run("make evil").startswith("BLOCKED")


def test_gate_commands_are_qa_only_by_default():
    coder_shell = ShellTool(allow_gates=False)
    for command in ("pytest -q", "ruff check .", "npm --prefix frontend run lint"):
        assert coder_shell._run(command).startswith("BLOCKED: gates are QA-only")
    # Inspection and plain compilation stay available to the coder.
    assert coder_shell._run("git status").startswith("exit=")
    assert coder_shell._run("ls app").startswith("exit=")


def test_gate_classifier_scope():
    from swarm.tools_guarded import is_gate_command

    assert is_gate_command(["pytest", "-q"])
    assert is_gate_command(["npm", "--prefix", "frontend", "run", "lint"])
    assert is_gate_command(["npm", "--prefix", "frontend", "test", "--", "--run"])
    assert not is_gate_command(["npm", "--prefix", "frontend", "run", "build"])
    assert not is_gate_command(["git", "status"])
    assert not is_gate_command([])


def test_qa_shell_can_run_gates():
    assert ShellTool()._run("pytest -q").startswith("exit=")


def test_format_is_allowed_but_install_is_not():
    shell = ShellTool(allow_gates=False)
    assert shell._run("npm --prefix frontend run format").startswith(("exit=", "BLOCKED: timeout"))
    assert shell._run("npm --prefix frontend install").startswith("BLOCKED")
