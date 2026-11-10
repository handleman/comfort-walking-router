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

    stub = type("S", (), {})()
    stub.run_dir = Path("20261110-120000-new")
    stub._stash_ref = "swarm-20261110-111956-run"
    stub._stash_sha = sha
    stub.state = flow.SwarmState()
    stub._unmerged_paths = lambda: flow._unmerged_paths()

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

    stub = type("S", (), {})()
    stub.run_dir = Path("20261110-120000-new")
    stub._stash_ref = "swarm-run"
    stub._stash_sha = sha
    stub.state = flow.SwarmState()
    stub._unmerged_paths = lambda: flow._unmerged_paths()

    flow.SwarmFlow._restore_stash(stub)

    assert stub.state.stash_conflict == ["a.txt"]
    assert stub.state.stash_conflict_ref == ""
    assert (repo / "a.txt").read_text() == "c\n"
    assert git(repo, "diff", "--name-only", "--diff-filter=U") == ""
    # Nothing deleted: the stash is still there for the operator.
    assert [e["message"] for e in stashes.list_stashes(repo)] == ["swarm-run"]
