"""Escape-rate tests (024): merged (green) commits vs later reverts."""

from __future__ import annotations

import subprocess
from pathlib import Path

from swarm import escape


def _git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return p.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@e.com")
    _git(repo, "config", "user.name", "T")
    (repo / "x.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base\n\nSwarm-Task: 001/T1")
    return repo


def _row(task: str, cls: int = 1) -> dict:
    return {"spec": "001", "task": task, "status": "green", "risk": {"class": cls}}


def test_no_merged_runs_is_not_an_escape(tmp_path: Path):
    result = escape.rate([{"status": "needs_human"}], repo=_repo(tmp_path))
    assert result["merged"] == 0 and result["rate"] == 0.0
    assert "no merged runs" in escape.render(result)


def test_a_reverted_auto_merge_counts(tmp_path: Path):
    repo = _repo(tmp_path)
    sha = _git(repo, "rev-parse", "HEAD")
    result = escape.rate([_row("T1")], repo=repo)
    assert result["merged"] == 1 and result["escapes"] == 0

    _git(repo, "revert", "--no-edit", sha)
    result = escape.rate([_row("T1")], repo=repo)
    assert result["escapes"] == 1 and result["rate"] == 1.0
    assert result["by_class"]["class 1"] == {"merged": 1, "escapes": 1}
    assert "1/1" in escape.render(result)


def test_a_non_green_run_is_ignored(tmp_path: Path):
    repo = _repo(tmp_path)
    row = {"spec": "001", "task": "T1", "status": "needs_human", "risk": {"class": 3}}
    assert escape.rate([row], repo=repo)["merged"] == 0


def test_the_report_prints_the_ratio():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "report.py").read_text()
    assert "escape.rate(rows)" in source
    assert "escape.render(result)" in source
