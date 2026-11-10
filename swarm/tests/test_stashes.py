"""Stash lifecycle: orphaned `swarm-*` stashes are archived, never dropped blindly."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from swarm import stashes

IDENTITY = ("-c", "user.email=swarm@example.test", "-c", "user.name=swarm-test")


def git(repo: Path, *args: str) -> str:
    p = subprocess.run(
        ["git", *IDENTITY, *args], cwd=repo, check=False, capture_output=True, text=True
    )
    assert p.returncode == 0, p.stderr
    return p.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a.txt").write_text("a\n")
    git(tmp_path, "add", "a.txt")
    git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def stash(repo: Path, message: str, content: str = "b\n") -> None:
    (repo / "a.txt").write_text(content)
    git(repo, "stash", "push", "-q", "-m", message)


def stash_messages(repo: Path) -> list[str]:
    return [e["message"] for e in stashes.list_stashes(repo)]


def test_list_stashes_reports_ref_sha_and_message(repo: Path) -> None:
    stash(repo, "swarm-20261110-111956-run")
    stash(repo, "WIP user work")

    entries = stashes.list_stashes(repo)

    assert [e["message"] for e in entries] == ["WIP user work", "swarm-20261110-111956-run"]
    assert entries[0]["ref"] == "stash@{0}"
    assert all(len(e["sha"]) == 40 for e in entries)


def test_swarm_stashes_never_selects_a_user_entry(repo: Path) -> None:
    stash(repo, "swarm-run-1")
    stash(repo, "WIP keep me")

    picked = stashes.swarm_stashes(stashes.list_stashes(repo))

    assert [e["message"] for e in picked] == ["swarm-run-1"]


def test_sweep_archives_orphans_and_leaves_user_stashes_alone(repo: Path) -> None:
    stash(repo, "swarm-20261110-041814-run", "b\n")
    stash(repo, "WIP keep me", "user\n")

    archived = stashes.sweep(repo, run_id="20261110-120000-new")

    assert len(archived) == 1
    record = archived[0]
    assert record["reason"] == "orphaned"
    assert record["run"] == "20261110-120000-new"
    assert record["ref"].startswith("refs/swarm/archive/")
    assert record["sha"] in git(repo, "rev-parse", "--verify", record["ref"])
    # Content survived: the ref is a readable stash commit.
    assert "b" in git(repo, "show", f"{record['ref']}:a.txt")
    # The stack is clean but the user's stash is untouched.
    assert stash_messages(repo) == ["WIP keep me"]
    # …and the archive is indexed for later inspection.
    ledger = json.loads((repo / stashes.DEFAULT_LEDGER).read_text())
    assert [r["ref"] for r in ledger["archived"]] == [record["ref"]]


def test_sweep_archives_every_orphan_even_after_renumbering(repo: Path) -> None:
    stash(repo, "swarm-first", "b\n")
    (repo / "b.txt").write_text("other\n")
    git(repo, "add", "b.txt")
    git(repo, "stash", "push", "-q", "-m", "swarm-second")

    archived = stashes.sweep(repo, run_id="r")

    assert len(archived) == 2
    assert stashes.list_stashes(repo) == []
    for record in archived:
        assert record["sha"] in git(repo, "rev-parse", "--verify", record["ref"])


def test_sweep_is_a_noop_without_swarm_stashes(repo: Path) -> None:
    stash(repo, "WIP keep me")

    assert stashes.sweep(repo, run_id="r") == []
    assert stash_messages(repo) == ["WIP keep me"]


def test_archive_records_the_reason_and_the_files(repo: Path) -> None:
    stash(repo, "swarm-run", "b\n")
    entry = next(e for e in stashes.list_stashes(repo) if e["message"] == "swarm-run")

    record = stashes.archive(repo, entry, run_id="r", reason="conflict")

    assert record["reason"] == "conflict"
    assert record["files"] == ["a.txt"]
    assert record["message"] == "swarm-run"
    assert stashes.list_stashes(repo) == []


def test_restore_conflict_archives_the_kept_stash(repo: Path, monkeypatch) -> None:
    """A conflicted pop keeps the work as a ref and records where it went."""
    from swarm import flow

    stash(repo, "swarm-20261110-111956-run", "b\n")
    sha = git(repo, "rev-parse", "refs/stash").strip()
    (repo / "a.txt").write_text("c\n")
    git(repo, "commit", "-qam", "base moved on")

    monkeypatch.setattr(flow, "REPO_ROOT", repo)
    monkeypatch.setenv("SWARM_ARCHIVE_STASHES", "1")
    monkeypatch.setenv("SWARM_CONFLICT_CREW", "0")

    stub = type("S", (), {})()
    stub.run_dir = Path("20261110-120000-new")
    stub._stash_ref = "swarm-20261110-111956-run"
    stub._stash_sha = sha
    stub.state = flow.SwarmState()
    stub._unmerged_paths = lambda: flow._unmerged_paths()
    stub._resolve_stash_conflict = lambda conflicts, **k: flow.SwarmFlow._resolve_stash_conflict(
        stub, conflicts, **k
    )

    flow.SwarmFlow._restore_stash(stub)

    assert stub._stash_ref == ""
    assert stub.state.stash_conflict == ["a.txt"]
    ref = stub.state.stash_conflict_ref
    assert ref.startswith("refs/swarm/archive/")
    assert sha in git(repo, "rev-parse", "--verify", ref)
    # The current worktree wins, no `UU` survives, and the stack is clean.
    assert (repo / "a.txt").read_text() == "c\n"
    assert git(repo, "diff", "--name-only", "--diff-filter=U") == ""
    assert stashes.list_stashes(repo) == []


def test_restore_conflict_falls_back_when_archiving_is_disabled(repo: Path, monkeypatch) -> None:
    from swarm import flow

    stash(repo, "swarm-run", "b\n")
    sha = git(repo, "rev-parse", "refs/stash").strip()
    (repo / "a.txt").write_text("c\n")
    git(repo, "commit", "-qam", "base moved on")

    monkeypatch.setattr(flow, "REPO_ROOT", repo)
    monkeypatch.setenv("SWARM_ARCHIVE_STASHES", "0")
    monkeypatch.setenv("SWARM_CONFLICT_CREW", "0")

    stub = type("S", (), {})()
    stub.run_dir = Path("20261110-120000-new")
    stub._stash_ref = "swarm-run"
    stub._stash_sha = sha
    stub.state = flow.SwarmState()
    stub._unmerged_paths = lambda: flow._unmerged_paths()
    stub._resolve_stash_conflict = lambda conflicts, **k: flow.SwarmFlow._resolve_stash_conflict(
        stub, conflicts, **k
    )

    flow.SwarmFlow._restore_stash(stub)

    assert stub.state.stash_conflict == ["a.txt"]
    assert stub.state.stash_conflict_ref == ""
    assert (repo / "a.txt").read_text() == "c\n"
    assert git(repo, "diff", "--name-only", "--diff-filter=U") == ""
    # Nothing deleted: the stash is still there for the operator.
    assert [e["message"] for e in stashes.list_stashes(repo)] == ["swarm-run"]


class _FakeCrew:
    def __init__(self, on_kickoff):
        self.agents = []
        self._on_kickoff = on_kickoff
        self.calls = 0

    def kickoff(self):
        self.calls += 1
        self._on_kickoff()
        return object()


def _conflicted_repo(repo: Path) -> str:
    """Parked work on the old base; HEAD then rewrote the same line."""
    stash(repo, "swarm-parked", "b\n")
    sha = git(repo, "rev-parse", "refs/stash").strip()
    (repo / "a.txt").write_text("c\n")
    git(repo, "commit", "-qam", "base moved on")
    return sha


def _restore_stub(repo: Path, sha: str, monkeypatch):
    from swarm import flow

    monkeypatch.setattr(flow, "REPO_ROOT", repo)
    monkeypatch.setenv("SWARM_ARCHIVE_STASHES", "1")
    monkeypatch.setenv("SWARM_CONFLICT_CREW", "1")
    monkeypatch.setattr(flow, "_run_gate_commands", lambda: [("pytest -q", 0, "")])

    stub = type("S", (), {})()
    stub._record_usage = lambda *a, **k: None
    stub.run_dir = Path("20261110-120000-new")
    stub._stash_ref = "swarm-parked"
    stub._stash_sha = sha
    stub.state = flow.SwarmState()
    stub._unmerged_paths = lambda: flow._unmerged_paths()
    stub._resolve_stash_conflict = lambda conflicts, **k: flow.SwarmFlow._resolve_stash_conflict(
        stub, conflicts, **k
    )
    return stub


def _patch_crew(monkeypatch, on_kickoff) -> _FakeCrew:
    from swarm import crew as crew_mod

    fake = _FakeCrew(on_kickoff)

    def build(*args, **kwargs):
        fake.kwargs = kwargs
        return fake

    monkeypatch.setattr(crew_mod, "build_stash_crew", build)
    return fake


def _ledger(repo: Path) -> list[dict]:
    path = repo / stashes.DEFAULT_LEDGER
    return json.loads(path.read_text())["archived"] if path.is_file() else []


def test_restore_conflict_is_resolved_by_the_crew(repo: Path, monkeypatch) -> None:
    from swarm import flow

    sha = _conflicted_repo(repo)
    fake = _patch_crew(monkeypatch, lambda: (repo / "a.txt").write_text("b\nc\n"))
    stub = _restore_stub(repo, sha, monkeypatch)
    flow.SwarmFlow._restore_stash(stub)

    assert fake.calls == 1
    assert fake.kwargs["stash"] == "swarm-parked"
    # Both sides survived, no marker is left and no `UU` stage remains.
    assert (repo / "a.txt").read_text() == "b\nc\n"
    assert git(repo, "diff", "--name-only", "--diff-filter=U") == ""
    # The parked work is an ordinary unstaged change, like a successful pop.
    assert git(repo, "diff", "--name-only").strip() == "a.txt"
    assert stub.state.stash_conflict_resolution == "crew"
    assert stub.state.stash_conflict_ref.startswith("refs/swarm/archive/")
    assert _ledger(repo)[-1]["reason"] == "resolved"
    assert stashes.list_stashes(repo) == []


def test_resolver_markers_fall_back_to_the_current_worktree(repo: Path, monkeypatch) -> None:
    from swarm import flow

    sha = _conflicted_repo(repo)
    _patch_crew(
        monkeypatch,
        lambda: (repo / "a.txt").write_text("<<<<<<< Updated upstream\nc\n=======\nb\n>>>>>>> Stashed\n"),
    )

    stub = _restore_stub(repo, sha, monkeypatch)
    flow.SwarmFlow._restore_stash(stub)

    assert (repo / "a.txt").read_text() == "c\n"
    assert git(repo, "diff", "--name-only", "--diff-filter=U") == ""
    assert stub.state.stash_conflict_resolution == "ours"
    assert "markers" in stub.state.stash_conflict_note
    assert _ledger(repo)[-1]["reason"] == "conflict"


def test_resolver_gate_failure_falls_back_to_the_current_worktree(repo: Path, monkeypatch) -> None:
    from swarm import flow

    (repo / "b.txt").write_text("base\n")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-qm", "add b")
    sha = _conflicted_repo(repo)
    _patch_crew(monkeypatch, lambda: (repo / "a.txt").write_text("b\nc\n"))
    stub = _restore_stub(repo, sha, monkeypatch)
    monkeypatch.setattr(flow, "_run_gate_commands", lambda: [("pytest -q", 1, "boom")])
    flow.SwarmFlow._restore_stash(stub)

    assert (repo / "a.txt").read_text() == "c\n"
    assert stub.state.stash_conflict_resolution == "ours"
    assert "failed gates" in stub.state.stash_conflict_note


def test_resolver_edits_outside_the_conflict_are_reverted(repo: Path, monkeypatch) -> None:
    from swarm import flow

    (repo / "b.txt").write_text("base\n")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-qm", "add b")
    sha = _conflicted_repo(repo)

    def kickoff():
        (repo / "a.txt").write_text("b\nc\n")
        (repo / "b.txt").write_text("crew wrote this\n")

    _patch_crew(monkeypatch, kickoff)
    stub = _restore_stub(repo, sha, monkeypatch)
    flow.SwarmFlow._restore_stash(stub)

    assert stub.state.stash_conflict_resolution == "ours"
    assert "outside the conflict" in stub.state.stash_conflict_note
    assert (repo / "b.txt").read_text() == "base\n"
    assert (repo / "a.txt").read_text() == "c\n"


def test_resolver_is_disabled_by_env(repo: Path, monkeypatch) -> None:
    from swarm import flow

    sha = _conflicted_repo(repo)
    fake = _patch_crew(monkeypatch, lambda: (repo / "a.txt").write_text("b\nc\n"))
    stub = _restore_stub(repo, sha, monkeypatch)
    monkeypatch.setenv("SWARM_CONFLICT_CREW", "0")

    flow.SwarmFlow._restore_stash(stub)

    assert fake.calls == 0
    assert (repo / "a.txt").read_text() == "c\n"
    assert stub.state.stash_conflict_resolution == "ours"
    assert "disabled" in stub.state.stash_conflict_note


def test_cleanup_never_kicks_a_crew(repo: Path, monkeypatch) -> None:
    from swarm import flow

    sha = _conflicted_repo(repo)
    fake = _patch_crew(monkeypatch, lambda: (repo / "a.txt").write_text("b\nc\n"))
    stub = _restore_stub(repo, sha, monkeypatch)

    flow.SwarmFlow._restore_stash(stub, allow_crew=False)

    assert fake.calls == 0
    assert (repo / "a.txt").read_text() == "c\n"
    assert "cleanup" in stub.state.stash_conflict_note
