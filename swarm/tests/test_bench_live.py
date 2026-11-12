"""Live-replay guards and plumbing (020 T7). No model runs in this test."""

from __future__ import annotations

from pathlib import Path

from swarm.bench import live


def _git(repo: Path, *args: str) -> tuple[int, str]:
    return live._git(repo, *args)


def test_preflight_refuses_a_dirty_tree(monkeypatch):
    monkeypatch.setattr(live, "_git", lambda repo, *a: (0, " M app/scoring.py\n"))
    assert "dirty tree" in (live.preflight(Path(".")) or "")


def test_preflight_refuses_a_linked_worktree(monkeypatch):
    def fake(repo, *args):
        if args[1] == "--git-dir":
            return 0, "/repo/.git/worktrees/wt\n"
        if args[1] == "--git-common-dir":
            return 0, "/repo/.git\n"
        return 0, ""

    monkeypatch.setattr(live, "_git", fake)
    assert "linked worktree" in (live.preflight(Path(".")) or "")


def test_preflight_passes_a_clean_primary_checkout(monkeypatch):
    monkeypatch.setattr(live, "_git", lambda repo, *a: (0, ""))
    assert live.preflight(Path(".")) is None


def test_unknown_case_is_refused_before_any_worktree(monkeypatch):
    called: list[tuple] = []
    monkeypatch.setattr(live.corpus, "load_corpus", lambda repo: [])
    monkeypatch.setattr(live, "_git", lambda repo, *a: called.append(a) or (0, ""))
    result = live.run_case("no-such-case", repo=Path("."))
    assert result["ok"] is False and "unknown case" in result["error"]
    assert called == []


def test_a_dirty_tree_is_refused_by_run_case(monkeypatch):
    case = {"id": "x", "spec": "s", "task": "T1", "base_sha": "abc"}
    monkeypatch.setattr(live.corpus, "load_corpus", lambda repo: [case])
    monkeypatch.setattr(live, "_git", lambda repo, *a: (0, " M file\n"))
    result = live.run_case("x", repo=Path("."))
    assert result["ok"] is False and "dirty tree" in result["error"]


def test_copy_harness_skips_runs_and_vendor(tmp_path: Path):
    repo = tmp_path / "repo"
    source = repo / "swarm"
    (source / "bench" / "corpus").mkdir(parents=True)
    (source / "runs" / "20260101").mkdir(parents=True)
    (source / "__pycache__").mkdir()
    (source / "flow.py").write_text("x = 1\n")
    (source / "bench" / "corpus" / "c.json").write_text("{}")
    (source / "runs" / "20260101" / "run.json").write_text("{}")

    destination = tmp_path / "wt"
    skipped = live.copy_harness(repo, destination)

    assert (destination / "swarm" / "flow.py").read_text() == "x = 1\n"
    assert not (destination / "swarm" / "runs").exists()
    assert not (destination / "swarm" / "bench" / "corpus").exists()
    assert not (destination / "swarm" / "__pycache__").exists()
    assert "runs" in skipped and "bench/corpus" in skipped


def test_model_pins_map_to_role_env():
    env = {"SWARM_BENCH_MODELS": "coder=ollama/a, qa=ollama/b,planner=ollama/c,senior=ollama/d"}
    assert live.model_env(env) == {
        "SWARM_CODER_MODEL": "ollama/a",
        "SWARM_REVIEWER_MODEL": "ollama/b",
        "SWARM_PLANNER_MODEL": "ollama/c",
        "SWARM_SENIOR_MODEL": "ollama/d",
    }
    assert live.model_env({}) == {}


def test_render_shows_the_measured_numbers():
    ok = {
        "ok": True,
        "case": "006-comfort-plus-T3",
        "duration_seconds": 300,
        "prompt_tokens": 12345,
        "cached_prompt_tokens": 9000,
        "cost_usd": 0.0,
        "fix_rounds": 1,
        "gates": {"pytest -q": 0},
    }
    text = live.render(ok)
    assert "green in 300s" in text and "12,345" in text and "9,000 cached" in text
    assert "FAILED" in live.render({"ok": False, "case": "x", "error": "dirty tree"})


def test_live_replay_is_not_part_of_the_test_suite():
    """The CLI exists, but nothing runs a model unless asked explicitly."""
    from swarm.bench.__main__ import main

    assert main(["--live", "no-such-case"]) == 1


def test_makefile_has_the_live_target():
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text()
    assert "swarm-bench-live:" in makefile and "--live $(CASE)" in makefile
