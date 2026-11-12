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


def test_truncated_read_names_the_line_to_continue_from(tmp_path):
    """014-T1 (2026-11-12) re-read the same head of a file seven times.

    The old note said "re-read with start_line/line_count" without saying
    where, so the model re-read from line 1 and changed nothing. The note
    must name the exact next line.
    """
    big = tmp_path / "big.txt"
    big.write_text("".join(f"line {n}\n" for n in range(1, 400)))
    out = TrimmedFileReadTool(base_dir=str(tmp_path))._run(
        file_path=str(big), start_line=1, line_count=400
    )
    assert "CONTINUE with start_line=" in out
    resume = int(out.split("CONTINUE with start_line=")[1].split(" ")[0])
    assert resume > 1
    # The resumed read must return content the first read did not show.
    second = TrimmedFileReadTool(base_dir=str(tmp_path))._run(
        file_path=str(big), start_line=resume, line_count=400
    )
    assert second.startswith(f"line {resume}")


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
