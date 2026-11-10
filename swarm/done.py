"""Done ledger for green tasks (013 T1/T3).

The swarm never edits `specs/`, so a green task can stay `- [ ]`. Completion is
recorded in git commit trailers instead:

    Swarm-Task: 001-example-app/T3
    Swarm-Task-Hash: <sha256 of task id+brief+ACs>
    Swarm-Spec-Hash: <sha256 of spec.md+plan.md>
    Swarm-Run: <run dir name>

A task counts as done only when both hashes still match. Editing `spec.md` or
`plan.md` reopens it; marking `[x]` in `tasks.md` does not change either hash.
A gitignored `swarm/runs/done.json` cache is a fallback for shallow/rewritten
history; git trailers remain the source of truth when present.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_HASH_FILES = ("spec.md", "plan.md")

_TASK_RE = re.compile(r"^Swarm-Task:\s*(\S+)/(T\d+)\s*$", re.MULTILINE)
_TASK_HASH_RE = re.compile(r"^Swarm-Task-Hash:\s*([0-9a-f]{8,64})\s*$", re.MULTILINE)
_SPEC_HASH_RE = re.compile(r"^Swarm-Spec-Hash:\s*([0-9a-f]{8,64})\s*$", re.MULTILINE)


@dataclass(frozen=True)
class DoneEntry:
    task_hash: str
    spec_hash: str = ""
    run: str = ""
    source: str = "git"


def _norm(text: str) -> str:
    return " ".join(text.split())


def task_hash(task: Any) -> str:
    """Stable hash of the task's identity + brief + AC refs."""
    payload = "\n".join(
        [str(task.id).strip(), _norm(str(task.brief)), ",".join(sorted(getattr(task, "ac_refs", ())))]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def spec_plan_hash(spec_path: Path) -> str:
    """Hash `spec.md` + `plan.md` only (not tasks.md, so `[x]` does not reopen)."""
    h = hashlib.sha256()
    for name in SPEC_HASH_FILES:
        h.update(name.encode())
        h.update(b"\0")
        p = spec_path / name
        h.update(p.read_bytes() if p.is_file() else b"")
        h.update(b"\0")
    return h.hexdigest()


def _key(spec_dir: str, task_id: str) -> str:
    return f"{spec_dir}/{task_id}"


def _cache_path(repo_root: Path) -> Path:
    return repo_root / "swarm" / "runs" / "done.json"


def _read_cache(repo_root: Path) -> dict[str, dict[str, str]]:
    try:
        raw = json.loads(_cache_path(repo_root).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def record_done(
    repo_root: Path,
    spec_dir: str,
    task_id: str,
    *,
    task_hash_value: str,
    spec_hash_value: str,
    run_id: str,
) -> None:
    """Write the local fallback cache (git trailers are written by the commit)."""
    cache = _read_cache(repo_root)
    cache[_key(spec_dir, task_id)] = {
        "task_hash": task_hash_value,
        "spec_hash": spec_hash_value,
        "run": run_id,
    }
    path = _cache_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=2, sort_keys=True))
    os.replace(tmp, path)


def _git_entries(repo_root: Path, limit: int = 1000) -> dict[str, DoneEntry]:
    try:
        p = subprocess.run(
            ["git", "log", f"-n{limit}", "--format=%B%x00", "--grep=Swarm-Task:"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if p.returncode != 0:
        return {}
    entries: dict[str, DoneEntry] = {}
    for block in p.stdout.split("\0"):
        mt = _TASK_RE.search(block)
        mh = _TASK_HASH_RE.search(block)
        if not mt or not mh:
            continue
        ms = _SPEC_HASH_RE.search(block)
        key = _key(mt.group(1), mt.group(2))
        entries.setdefault(
            key,
            DoneEntry(
                task_hash=mh.group(1),
                spec_hash=ms.group(1) if ms else "",
                source="git",
            ),
        )
    return entries


def done_entries(repo_root: Path | None = None) -> dict[str, DoneEntry]:
    """Newest done entry per task: git trailers first, local cache for gaps.

    Keys are canonicalised to `<spec-dir>/<task>`: older commits recorded the
    invocation prefix (`007/T5`), which never matched the dir name the queue
    asks for, so a green task looked open and was re-run (007-T5, 2026-11-10).
    Newer entries win because `_git_entries` walks `git log` newest first.
    """
    from swarm.spec_loader import spec_dir_name

    root = repo_root or REPO_ROOT
    entries = _git_entries(root)
    for key, rec in _read_cache(root).items():
        if key in entries or not isinstance(rec, dict):
            continue
        entries[key] = DoneEntry(
            task_hash=str(rec.get("task_hash", "")),
            spec_hash=str(rec.get("spec_hash", "")),
            run=str(rec.get("run", "")),
            source="cache",
        )
    normalised: dict[str, DoneEntry] = {}
    for key, entry in entries.items():
        spec, _, task = key.partition("/")
        normalised.setdefault(_key(spec_dir_name(root, spec), task), entry)
    return normalised


def is_done(
    entries: dict[str, DoneEntry],
    spec_dir: str,
    task: Any,
    current_spec_hash: str,
) -> bool:
    """True when task+spec content still match the recorded green commit."""
    entry = entries.get(_key(spec_dir, str(task.id)))
    if entry is None or entry.task_hash != task_hash(task):
        return False
    # Entries predating the spec hash stay valid (task hash is still exact).
    return not entry.spec_hash or entry.spec_hash == current_spec_hash
