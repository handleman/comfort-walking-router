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


def test_link_venvs_reuses_the_repo_trees(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "swarm" / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / "frontend" / "node_modules").mkdir(parents=True)
    worktree = tmp_path / "wt"
    (worktree / "swarm").mkdir(parents=True)

    linked = live.link_venvs(repo, worktree)
    assert linked == [".venv", "swarm/.venv", "frontend/node_modules"]
    assert (worktree / "swarm" / ".venv").is_symlink()
    assert (worktree / ".venv").resolve() == (repo / ".venv").resolve()
    # idempotent: a second call changes nothing
    assert live.link_venvs(repo, worktree) == []


def test_fill_from_dotenv_keeps_explicit_pins_and_fills_the_rest(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("OPENROUTER_API_KEY=secret-value\nSWARM_PLANNER_MODEL=openrouter/p:free\n")
    env = {"SWARM_CODER_MODEL": "ollama/pinned"}
    filled = live.fill_from_dotenv(repo, env)
    assert set(filled) == {"OPENROUTER_API_KEY", "SWARM_PLANNER_MODEL"}
    assert env["OPENROUTER_API_KEY"] == "secret-value"
    assert env["SWARM_CODER_MODEL"] == "ollama/pinned"  # an explicit pin wins


def test_fill_from_dotenv_tolerates_a_missing_file(tmp_path: Path):
    env = {"A": "1"}
    assert live.fill_from_dotenv(tmp_path, env) == []
    assert env == {"A": "1"}


def test_the_replay_disables_stash_hygiene(tmp_path: Path):
    from pathlib import Path as P

    source = (P(__file__).resolve().parents[1] / "bench" / "live.py").read_text()
    assert '"SWARM_STASH_UNRELATED"] = "0"' in source


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


def test_a_killed_run_reports_its_last_phase(tmp_path: Path):
    run_dir = tmp_path / "swarm" / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (tmp_path / "swarm" / "runs" / "latest").write_text("r1")
    (run_dir / "events.jsonl").write_text(
        '{"type": "crew_started", "at": "2026-11-14T10:00:00.000", "role": "verifier"}\n'
        '{"type": "crew_done", "at": "2026-11-14T10:01:30.000", "role": "verifier"}\n'
    )
    last = live._last_phase(tmp_path)
    assert last["phase"] == "verifier"
    assert last["duration_seconds"] == 90.0


def test_a_timeout_record_is_explicit():
    source = (Path(__file__).resolve().parents[1] / "bench" / "live.py").read_text()
    assert '"status": "timeout"' in source
    assert '"last_phase": last.get("phase", "")' in source
