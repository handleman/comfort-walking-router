"""Escape-rate telemetry for earned autonomy (024).

Autonomy expands on measured agreement, not ambition: the metric that matters is
how often an auto-merged change had to be reverted afterwards. This module joins
`run.json.autonomy` (which runs were auto-merged) with git (which of their commits
were later reverted) and reports a ratio per risk class.

A revert is the explicit `This reverts commit <sha>` message git writes. A
hand-fixed regression is not detected here; the ratio is a floor, not a ceiling.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(repo: Path, *args: str) -> str:
    try:
        p = subprocess.run(
            ["git", *args], cwd=repo, check=False, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def auto_merged(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        info = row.get("autonomy") or {}
        if not info.get("auto_merge"):
            continue
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
    merged = auto_merged(rows)
    escapes = 0
    by_class: dict[str, dict[str, int]] = {}
    for entry in merged:
        key = f"class {entry['class']}"
        bucket = by_class.setdefault(key, {"auto_merged": 0, "escapes": 0})
        bucket["auto_merged"] += 1
        sha = commit_for(root, entry["spec"], entry["task"])
        if is_reverted(root, sha):
            escapes += 1
            bucket["escapes"] += 1
    return {
        "auto_merged": len(merged),
        "escapes": escapes,
        "rate": round(escapes / len(merged), 3) if merged else 0.0,
        "by_class": by_class,
    }


def render(result: dict[str, Any]) -> str:
    if not result.get("auto_merged"):
        return "autonomy escapes: no auto-merged runs yet"
    classes = ", ".join(
        f"{name} {bucket['escapes']}/{bucket['auto_merged']}"
        for name, bucket in sorted(result["by_class"].items())
    )
    return (
        f"autonomy escapes: {result['escapes']}/{result['auto_merged']} "
        f"({result['rate'] * 100:.0f}%) — {classes}"
    )
