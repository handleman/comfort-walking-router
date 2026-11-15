"""Escape-rate telemetry (024).

The swarm merges green runs by itself, so the honest question is not "did a
human approve?" but "did an automatic merge have to be reverted?". This module
joins `run.json` (every merged run and its risk label) with git (which of their
commits a later commit reverts) and reports a ratio per class.

It is a floor: a regression fixed by hand is not a detected escape.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(repo: Path, *args: str) -> str:
    try:
        p = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def merged(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Green runs — every one of them merges without a human."""
    out: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("status") or "") != "green":
            continue
        info = row.get("risk") or row.get("autonomy") or {}
        out.append(
            {
                "spec": str(row.get("spec") or ""),
                "task": str(row.get("task") or ""),
                "class": info.get("class"),
                "run": str(row.get("_run") or ""),
            }
        )
    return out


def commit_for(repo: Path, spec: str, task: str) -> str:
    """The newest commit carrying this task's done-ledger trailer."""
    out = _git(repo, "log", "-1", "--format=%H", f"--grep=Swarm-Task: {spec}/{task}")
    return out.splitlines()[0] if out else ""


def is_reverted(repo: Path, sha: str) -> bool:
    if not sha:
        return False
    return bool(_git(repo, "log", "--all", "--format=%H", f"--grep=This reverts commit {sha}"))


def rate(rows: list[dict[str, Any]], repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO_ROOT
    runs = merged(rows)
    escapes = 0
    by_class: dict[str, dict[str, int]] = {}
    for entry in runs:
        # Historic runs predate `run.json.risk`; do not print "class None".
        key = f"class {entry['class'] if entry['class'] is not None else 'n/a'}"
        bucket = by_class.setdefault(key, {"merged": 0, "escapes": 0})
        bucket["merged"] += 1
        sha = commit_for(root, entry["spec"], entry["task"])
        if is_reverted(root, sha):
            escapes += 1
            bucket["escapes"] += 1
    return {
        "merged": len(runs),
        "escapes": escapes,
        "rate": round(escapes / len(runs), 3) if runs else 0.0,
        "by_class": by_class,
    }


def render(result: dict[str, Any]) -> str:
    if not result.get("merged"):
        return "escapes: no merged runs yet"
    classes = ", ".join(
        f"{name} {bucket['escapes']}/{bucket['merged']}"
        for name, bucket in sorted(result["by_class"].items())
    )
    return (
        f"escapes: {result['escapes']}/{result['merged']} "
        f"({result['rate'] * 100:.0f}%) — {classes}"
    )
