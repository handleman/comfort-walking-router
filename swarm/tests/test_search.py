"""Search tool + report shape tests (020 T6/AC-5)."""

from __future__ import annotations

from pathlib import Path

from swarm.tools_guarded import (
    FullFileReadTool,
    SearchTool,
    TrimmedFileReadTool,
    coder_read_chars,
)

# ---- Repo Search ----


def test_search_returns_path_line_text():
    out = SearchTool()._run(r"def gate_commands\(", "swarm")
    assert out.startswith("swarm/flow.py:")
    line = out.splitlines()[0]
    assert ": " in line and "def gate_commands" in line


def test_search_is_bounded():
    out = SearchTool(max_results=3)._run(r"def ", "swarm")
    assert "stopped at 3 matches" in out
    assert len([ln for ln in out.splitlines() if ": " in ln]) == 3


def test_search_can_be_limited_to_a_file_and_reports_no_match():
    assert SearchTool()._run("select_gates", "swarm/gates.py").startswith("swarm/gates.py:")
    assert SearchTool()._run("zzz-not-there-zzz", "swarm/gates.py") == "(no matches for 'zzz-not-there-zzz')"


def test_search_refuses_escape_and_secrets():
    assert "outside the repo" in SearchTool()._run("x", "../")
    assert "secret" in SearchTool()._run("x", ".env").lower()


def test_search_rejects_a_bad_regex():
    assert "bad regex" in SearchTool()._run("([unclosed")


def test_search_skips_vendor_and_run_directories():
    out = SearchTool(max_results=200)._run(r"Swarm-Task", "")
    assert "node_modules" not in out
    assert "/swarm/runs/" not in out
    assert ".venv" not in out


def test_search_never_returns_a_secret_file():
    from swarm.tools_guarded import is_secret_path

    out = SearchTool(max_results=200)._run(r"OPENROUTER_API_KEY", "")
    paths = [line.split(":", 1)[0] for line in out.splitlines() if ": " in line]
    assert paths, "the pattern is documented somewhere, so the search is not vacuous"
    assert not any(is_secret_path(path) for path in paths)


# ---- coder read cap ----


def test_coder_read_cap_default_and_override(monkeypatch):
    monkeypatch.delenv("SWARM_CODER_READ_CHARS", raising=False)
    assert coder_read_chars() == 3000
    monkeypatch.setenv("SWARM_CODER_READ_CHARS", "9000")
    assert coder_read_chars() == 9000
    monkeypatch.setenv("SWARM_CODER_READ_CHARS", "nonsense")
    assert coder_read_chars() == 3000


def test_verifier_read_keeps_its_own_cap(monkeypatch):
    monkeypatch.setenv("SWARM_CODER_READ_CHARS", "9000")
    assert FullFileReadTool().env_cap is False
    assert TrimmedFileReadTool().env_cap is True
    assert int(FullFileReadTool().max_observation) >= 10000


def test_coders_get_search_qa_and_verifier_do_not():
    from swarm.crew import build_review_crew, build_step_crew, build_verify_crew
    from swarm.spec_loader import SpecTask

    task = SpecTask(id="T2", ac_refs=("AC-5",), brief="Fix `app/scoring.py`.")
    def names(crew):
        return [getattr(t, "name", "") for t in crew.agents[0].tools]
    assert "Repo Search" in names(build_step_crew("001", task, "Edit `app/scoring.py`.", 1, 1))
    assert "Repo Search" not in names(build_review_crew("001", task, "summary"))
    assert "Repo Search" not in names(build_verify_crew("001", task, "context"))


# ---- structured report ----


def _report(tail: str, exit_code: int = 1) -> dict:
    from swarm.evidence import qa_report, split_tails

    return qa_report(
        gates={"pytest -q": exit_code},
        tails=split_tails(f"$ pytest -q\nexit={exit_code}\n{tail}"),
        changed=["app/scoring.py"],
        verdict="fail",
        reason="blocked",
    )


def test_report_is_versioned_and_never_repeats_the_tail():
    from swarm.evidence import report_text

    tail = "\n".join(
        ["app/scoring.py:12: error: expected value", *("context line " * 5 for _ in range(30))]
    )
    report = _report(tail)
    text = report_text(report)
    assert report["version"] == 2
    assert "key lines:" in text
    assert "app/scoring.py:12" in text
    # the same failure is not pasted twice: no raw output section when key
    # lines exist
    assert "output:" not in text


def test_report_falls_back_to_raw_output_when_nothing_is_extractable():
    from swarm.evidence import report_text

    tail = "\n".join(f"plain line {n}" for n in range(40))
    text = report_text(_report(tail))
    assert "key lines:" not in text
    assert "output:" in text and "plain line 39" in text


def test_report_chars_is_recorded_by_the_flow():
    source = (Path(__file__).resolve().parents[1] / "flow.py").read_text()
    assert 'report["report_chars"] = len(report_text(report))' in source
