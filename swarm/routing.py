"""Cost routing for micro-steps (015 D2).

Decision D2: the paid coder does anything non-trivial; the local (free) coder is
reserved for mechanical steps. Ambiguity resolves to paid, and a trivial step
that turns red is retried paid.

The classifier is deliberately deterministic: no model call, no hidden cost, and
every decision is auditable in `run.json` (`model`, `routing_reason`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Tokens that mark a step as "logic", not mechanics. Matched case-insensitively.
LOGIC_WORDS = (
    "implement",
    "refactor",
    "handle",
    "validate",
    "parse",
    "async",
    "await",
    "fetch",
    "api",
    "endpoint",
    "query",
    "schema",
    "migration",
    "migrate",
    "assert",
    "test",
    "error",
    "exception",
    "retry",
    "cache",
    "algorithm",
    "optimis",
    "optimiz",
    "type",
    "interface",
    "score",
    "route",
    "calc",
)
FRONTEND_SUFFIXES = (".svelte", ".ts", ".tsx", ".js", ".jsx", ".css", ".html")
FRONTEND_DIRS = ("frontend/", "ui/", "src/")
EDIT_WORDS = ("edit", "update", "change", "modify", "fix", "adjust", "extend", "replace")
PATH_RE = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class Route:
    kind: str  # "paid" | "local"
    reason: str


def _paths(step: str) -> list[str]:
    raw = PATH_RE.findall(step or "")
    out: list[str] = []
    for candidate in raw:
        value = candidate.strip()
        if not value or " " in value:
            continue
        if "/" in value or "." in value:
            out.append(value)
    return out


def classify_step(
    step: str,
    *,
    repo_root: Path | None = None,
    attempt: int = 1,
    task_brief: str = "",
    enabled: bool = True,
) -> Route:
    """Decide paid vs local for one micro-step.

    Non-trivial (paid) when any of: retry attempt, >1 file, an existing file is
    edited, a frontend/type-checked path is touched, or the wording implies
    logic/tests/API/DB work. Trivial (local) only for a single *new* small file
    with mechanical wording.
    """
    if not enabled:
        return Route("paid", "routing disabled")
    if attempt > 1:
        return Route("paid", f"retry attempt {attempt}")
    text = f"{task_brief} {step}".lower()
    paths = _paths(step)
    if not paths:
        return Route("paid", "no file path in step")
    if len(paths) > 1:
        return Route("paid", f"{len(paths)} files")
    target = paths[0]
    if any(target.endswith(suffix) for suffix in FRONTEND_SUFFIXES):
        return Route("paid", "frontend/type-checked file")
    if any(part in target for part in FRONTEND_DIRS):
        return Route("paid", "frontend path")
    if any(word in text for word in LOGIC_WORDS):
        return Route("paid", "logic/tests/API wording")
    if any(word in text for word in EDIT_WORDS):
        return Route("paid", "edits existing content")
    if repo_root is not None and (repo_root / target).exists():
        return Route("paid", "existing file")
    if not any(word in text for word in ("create", "add", "new file")):
        return Route("paid", "unclear intent")
    return Route("local", "new file, mechanical step")


def routing_enabled() -> bool:
    """Kill switch: `SWARM_LOCAL_FIRST=0` (or `SWARM_PAID_ALWAYS=1`) forces paid."""
    import os

    if os.getenv("SWARM_PAID_ALWAYS", "0") == "1":
        return False
    return os.getenv("SWARM_LOCAL_FIRST", "1") == "1"
