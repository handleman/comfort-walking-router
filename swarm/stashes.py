"""Stash lifecycle for the swarm (016 follow-up).

The flow parks unrelated dirty work in a `swarm-*` stash before a run and
restores it afterwards. When that restore conflicts, the stash is kept for a
human — but nobody remembers it, and a stale entry can later be popped by hand
onto the wrong base.

This module makes orphaned stashes harmless and self-cleaning:

- an orphan (a `swarm-*` stash left by an earlier run) is preserved permanently
  as `refs/swarm/archive/<timestamp>-<sha>`, indexed in
  `swarm/runs/orphan_stashes.json`, then removed from the stash stack
- a stash whose pop conflicted is archived the same way, so the work is still
  recoverable while the stack stays clean

Content is never lost: refs survive GC and are readable with `git show <ref>`.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

PREFIXES = ("swarm-",)
DEFAULT_LEDGER = Path("swarm") / "runs" / "orphan_stashes.json"


def _git(repo_root: Path, args: list[str], timeout: int = 60) -> tuple[int, str]:
    p = subprocess.run(
        ["git", *args], cwd=repo_root, check=False, capture_output=True, text=True, timeout=timeout
    )
    return p.returncode, (p.stdout + p.stderr)


def list_stashes(repo_root: Path) -> list[dict[str, str]]:
    """Every stash entry with its ref, commit SHA, and reflog message."""
    rc, out = _git(repo_root, ["stash", "list", "--format=%gd%x00%H%x00%s"])
    if rc != 0:
        return []
    rows: list[dict[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\x00")
        if len(parts) != 3:
            continue
        ref, sha, subject = parts
        rows.append(
            {
                "ref": ref.strip(),
                "sha": sha.strip(),
                "message": subject.split(": ", 1)[-1].strip(),
                "subject": subject.strip(),
            }
        )
    return rows


def swarm_stashes(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    """Only the harness's own stashes; a user's `WIP` entry is never touched."""
    return [e for e in entries if e["message"].startswith(PREFIXES)]


def _append_ledger(repo_root: Path, ledger: Path, record: dict[str, str]) -> None:
    path = ledger if ledger.is_absolute() else repo_root / ledger
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    archived = data.get("archived")
    if not isinstance(archived, list):
        archived = []
    archived.append(record)
    data["archived"] = archived
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        tmp.replace(path)
    except OSError:
        pass


def archive(
    repo_root: Path,
    entry: dict[str, str],
    *,
    run_id: str,
    reason: str,
    ledger: Path = DEFAULT_LEDGER,
) -> dict[str, str]:
    """Keep the stash commit as a ref, index it, and drop it from the stack."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    ref = f"refs/swarm/archive/{stamp}-{entry['sha'][:8]}"
    rc, out = _git(repo_root, ["update-ref", ref, entry["sha"]])
    if rc != 0:
        raise RuntimeError(f"update-ref failed: {out.strip()[:200]}")
    rc, out = _git(repo_root, ["show", "--name-only", "--pretty=format:", entry["sha"]])
    files = [line.strip() for line in out.splitlines() if line.strip()]
    record = {
        "ref": ref,
        "sha": entry["sha"],
        "message": entry["message"],
        "files": files,
        "run": run_id,
        "reason": reason,
        "archived_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    _append_ledger(repo_root, ledger, record)
    _git(repo_root, ["stash", "drop", entry["ref"]])
    return record


def sweep(repo_root: Path, *, run_id: str, ledger: Path = DEFAULT_LEDGER) -> list[dict[str, str]]:
    """Archive every `swarm-*` stash left by earlier runs (re-list after each drop).

    Dropping `stash@{0}` renumbers the stack, so the loop always takes the first
    current match instead of iterating over stale refs.
    """
    archived: list[dict[str, str]] = []
    while True:
        entries = swarm_stashes(list_stashes(repo_root))
        if not entries:
            return archived
        try:
            archived.append(
                archive(repo_root, entries[0], run_id=run_id, reason="orphaned", ledger=ledger)
            )
        except (RuntimeError, OSError):
            return archived
