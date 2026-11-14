"""Deterministic guards around model phases (026).

The first guard is the delta guard. Two 014-T10 runs spent 21 and 28 minutes,
produced `changed: []`, and then paid a verifier to tell us the files the brief
named were missing. 007-T10 and 014-T2 are the same shape: the module exists but
nothing mounts it.

The check is deliberately cheap and model-free:

* an empty in-scope delta is `no_delta`;
* a named path that does not exist before the run and is still absent is
  `delta_incomplete` (a *create* deliverable that was not created);
* a named path that already existed and was not touched is recorded as
  `untouched` but does not stop the run — briefs also name files for context,
  and the verifier still judges whether an update was required.

`SWARM_DELTA_GUARD=0` restores the old behaviour.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

DISABLE_ENV = "SWARM_DELTA_GUARD"


def enabled(env: Mapping[str, str] | None = None) -> bool:
    source: Mapping[str, str] = os.environ if env is None else env
    return str(source.get(DISABLE_ENV, "1")).strip().lower() not in {"0", "false", "no"}


def delta_record(
    brief: str,
    changed: Iterable[str],
    repo_root: Path,
) -> dict[str, Any]:
    """Describe this run's delta against the files the brief names.

    `changed` must be the run's in-scope delta (not the whole dirty tree): an
    operator edit is not the coder's work and must not make a run look complete.
    """
    from swarm.prompts import brief_paths

    touched = sorted({str(path).strip() for path in changed if str(path).strip()})
    named = brief_paths(brief)
    missing = [
        path for path in named if path not in touched and not (repo_root / path).exists()
    ]
    untouched = [
        path for path in named if path not in touched and (repo_root / path).exists()
    ]
    if not touched:
        reason = "no_delta"
    elif missing:
        reason = "delta_incomplete"
    else:
        reason = ""
    return {
        "reason": reason,
        "changed": touched,
        "named": named,
        "missing": missing,
        "untouched": untouched,
    }


def summary(record: Mapping[str, Any]) -> str:
    """One line for `human_log.txt` / the terminal."""
    reason = record.get("reason") or "ok"
    if reason == "no_delta":
        return "delta guard: the coding phase produced no in-scope change"
    if reason == "delta_incomplete":
        missing = ", ".join(record.get("missing") or [])
        return f"delta guard: brief-named files were not created: {missing}"
    untouched = record.get("untouched") or []
    tail = f" (named but untouched: {', '.join(untouched)})" if untouched else ""
    return f"delta guard: ok — {len(record.get('changed') or [])} changed path(s){tail}"
