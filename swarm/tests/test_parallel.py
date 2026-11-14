"""Parallel batch tests (023 phase 1): race, serialized integration, rollback."""

from __future__ import annotations

import subprocess
from pathlib import Path

from swarm import parallel


def _git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return p.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "app").mkdir()
    (repo / "app" / "x.py").write_text("x = 1\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    (repo / "specs" / "001-demo").mkdir(parents=True)
    (repo / "specs" / "001-demo" / "spec.md").write_text("# Spec\n")
    (repo / "specs" / "001-demo" / "plan.md").write_text("# Plan\n")
    (repo / "specs" / "001-demo" / "tasks.md").write_text(
        "- [ ] T1 (AC-1): Add `app/x.py`.\n"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def test_independent_groups_disjoint_briefs_and_splits_overlaps(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "specs" / "001-demo" / "tasks.md").write_text(
        "- [ ] T1 (AC-1): Add `app/x.py`.\n"
        "- [ ] T2 (AC-1): Add `app/y.py`.\n"
        "- [ ] T3 (AC-1): Change `app/x.py` again.\n"
    )
    groups = parallel.independent(repo, [("001-demo", "T1"), ("001-demo", "T2"), ("001-demo", "T3")])
    together = [set(group) for group in groups]
    assert {("001-demo", "T1"), ("001-demo", "T2")} in together
    assert ("001-demo", "T3") not in together[0] or len(groups) > 1


def test_integrate_applies_a_green_delta_and_commits(tmp_path: Path):
    repo = _repo(tmp_path)
    result = parallel.WorkerResult(
        spec="001-demo", task="T1", ok=True, status="green",
        changed=["app/x.py"], diff="", run_dir=str(tmp_path / "run"),
    )
    result.diff = "diff --git a/app/x.py b/app/x.py\n--- a/app/x.py\n+++ b/app/x.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    out = parallel.integrate(result, repo=repo, commands=["python -c 'print(1)'"], push=False)
    assert out["status"] == "integrated"
    assert (repo / "app" / "x.py").read_text() == "x = 2\n"
    assert "Swarm-Task: 001-demo/T1" in _git(repo, "log", "-1", "--format=%B")


def test_a_failing_gate_rolls_the_patch_back(tmp_path: Path):
    repo = _repo(tmp_path)
    result = parallel.WorkerResult(
        spec="001-demo", task="T1", ok=True, status="green",
        changed=["app/x.py"], run_dir=str(tmp_path / "run"),
        diff="diff --git a/app/x.py b/app/x.py\n--- a/app/x.py\n+++ b/app/x.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
    )
    out = parallel.integrate(result, repo=repo, commands=["python -c 'import sys; sys.exit(1)'"], push=False)
    assert out["status"] == "gates_failed"
    assert (repo / "app" / "x.py").read_text() == "x = 1\n"
    assert _git(repo, "status", "--porcelain") == ""


def test_a_conflicting_patch_is_refused_without_writing(tmp_path: Path):
    repo = _repo(tmp_path)
    result = parallel.WorkerResult(
        spec="001-demo", task="T1", ok=True, status="green",
        changed=["app/x.py"], run_dir=str(tmp_path / "run"),
        diff="diff --git a/app/x.py b/app/x.py\n--- a/app/x.py\n+++ b/app/x.py\n@@ -1 +1 @@\n-y = 9\n+y = 2\n",
    )
    out = parallel.integrate(result, repo=repo, commands=[], push=False)
    assert out["status"] == "conflict"
    assert (repo / "app" / "x.py").read_text() == "x = 1\n"


def test_run_batch_integrates_greens_serially_and_keeps_reds_out(tmp_path: Path):
    repo = _repo(tmp_path)
    order: list[str] = []

    def runner(spec, task, **kwargs):
        order.append(f"run:{task}")
        return parallel.WorkerResult(spec=spec, task=task, ok=task == "T1", status="green" if task == "T1" else "needs_human")

    def integrator(result, **kwargs):
        order.append(f"integrate:{result.task}")
        return {"status": "integrated", "task": f"{result.spec}/{result.task}", "commit": "abc"}

    out = parallel.run_batch(
        [("001-demo", "T1"), ("001-demo", "T2")], repo=repo, workers=2,
        runner=runner, integrator=integrator,
    )
    assert out["integrated"] == 1
    assert any(row["status"] == "integrated" for row in out["rows"])
    assert any(row["status"] == "needs_human" for row in out["rows"])
    assert len([o for o in order if o.startswith("integrate:")]) == 1


def test_the_worker_never_writes_the_main_tree(tmp_path: Path):
    source = (Path(__file__).resolve().parents[1] / "parallel.py").read_text()
    assert '"worktree", "add", "--detach"' in source
    assert '"--no-commit", "--no-tui"' in source
    assert 'SWARM_STASH_UNRELATED"] = "0"' in source
