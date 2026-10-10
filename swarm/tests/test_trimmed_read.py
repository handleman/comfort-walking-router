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
