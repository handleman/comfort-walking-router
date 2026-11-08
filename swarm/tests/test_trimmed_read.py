from swarm.tools_guarded import MAX_OBSERVATION, TrimmedFileReadTool


def test_trims_long_observations(tmp_path):
    big = tmp_path / "big.txt"
    big.write_text("x" * (MAX_OBSERVATION + 500))
    out = TrimmedFileReadTool(base_dir=str(tmp_path))._run(file_path=str(big))
    assert len(out) < MAX_OBSERVATION + 500
    assert "truncated" in out


def test_passthrough_short_observations(tmp_path):
    small = tmp_path / "small.txt"
    small.write_text("hello")
    assert "hello" in TrimmedFileReadTool(base_dir=str(tmp_path))._run(file_path=str(small))


def test_read_blocks_secrets_and_escapes(tmp_path):
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=secret")
    tool = TrimmedFileReadTool(base_dir=str(tmp_path))
    for path in (str(tmp_path / ".env"), ".env", "../escape.txt", "/etc/passwd"):
        assert tool._run(file_path=path).startswith("BLOCKED"), path


def test_read_blocks_nested_env(tmp_path):
    nested = tmp_path / "app" / ".env.local"
    nested.parent.mkdir()
    nested.write_text("SECRET=1")
    assert TrimmedFileReadTool(base_dir=str(tmp_path))._run(file_path=str(nested)).startswith("BLOCKED")
