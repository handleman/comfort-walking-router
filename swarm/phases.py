"""Per-phase wall clock from `events.jsonl` (022 T1, AC-1).

The loop is ~10 sequential model phases, so the wall clock has to be attributable
to a phase, not just to the run. The listener already stamps every event with an
`at` time; this module pairs `crew_started` with the next `crew_done`/`crew_failed`
and reports the phase (the role recorded at kickoff) and its duration.

There is deliberately no second clock: `run.json.phases` is derived from the
event stream, so the dashboard, the report and the record cannot disagree.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _seconds(start: Any, end: Any) -> float:
    try:
        a = datetime.fromisoformat(str(start))
        b = datetime.fromisoformat(str(end))
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, (b - a).total_seconds()), 1)


def derive(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair crew start/end events into phases (a stack handles nesting)."""
    open_phases: list[dict[str, Any]] = []
    out: list[dict[str, Any]] = []
    for event in events or []:
        kind = str(event.get("type") or "")
        if kind == "crew_started":
            open_phases.append(
                {
                    "phase": str(event.get("role") or event.get("agent") or "crew"),
                    "started_at": event.get("at"),
                    "model": event.get("model") or "",
                }
            )
        elif kind in {"crew_done", "crew_failed"}:
            if not open_phases:
                continue
            started = open_phases.pop()
            out.append(
                {
                    "phase": started["phase"],
                    "started_at": started["started_at"],
                    "ended_at": event.get("at"),
                    "duration_seconds": _seconds(started["started_at"], event.get("at")),
                    "failed": kind == "crew_failed",
                    "model": started.get("model") or "",
                }
            )
    return out


def totals(phases: list[dict[str, Any]]) -> dict[str, Any]:
    """Wall clock and the slowest phase, for `run.json.phases_total`."""
    total = round(sum(float(p.get("duration_seconds") or 0) for p in phases), 1)
    slowest = max(phases, key=lambda p: float(p.get("duration_seconds") or 0), default=None)
    return {
        "total_seconds": total,
        "slowest_phase": (slowest or {}).get("phase", ""),
        "slowest_seconds": float((slowest or {}).get("duration_seconds") or 0),
        "phases": len(phases),
    }
