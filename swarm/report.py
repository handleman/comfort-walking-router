"""Cost/autonomy report over recorded runs (015 AC-6).

`make swarm-report` → cost per green task, tokens per role, fix-round rate,
stop reasons, and p50/p90 wall clock. Pure read: never touches a run.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS = REPO_ROOT / "swarm" / "runs"


def collect(runs: Path = RUNS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not runs.is_dir():
        return rows
    for path in sorted(runs.iterdir()):
        if not path.is_dir() or not path.name[:1].isdigit():
            continue
        try:
            payload = json.loads((path / "run.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue
        payload["_run"] = path.name
        rows.append(payload)
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    green = [r for r in rows if r.get("status") == "green"]
    costs = [float(r.get("cost") or 0.0) for r in green if r.get("cost") is not None]
    durations = [
        float((r.get("usage") or {}).get("duration_seconds") or 0.0) for r in green
    ]
    durations = [d for d in durations if d > 0]
    reasons: dict[str, int] = {}
    for row in rows:
        if row.get("status") == "green":
            continue
        reason = str(row.get("reason_code") or row.get("status") or "unknown")
        reasons[reason] = reasons.get(reason, 0) + 1
    by_role: dict[str, dict[str, float]] = {}
    for row in rows:
        for role, usage in ((row.get("usage") or {}).get("by_role") or {}).items():
            bucket = by_role.setdefault(
                role, {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
            )
            bucket["prompt_tokens"] += float(usage.get("prompt_tokens") or 0)
            bucket["completion_tokens"] += float(usage.get("completion_tokens") or 0)
            bucket["cost_usd"] += float(usage.get("cost_usd") or 0.0)
    fix_rounds = [int(r.get("fix_rounds") or 0) for r in green]
    # 021 AC-2: why the repair rounds happened (mechanical labels).
    causes: dict[str, int] = {}
    phases: dict[str, int] = {}
    rounds = 0
    changed_rounds = 0
    for row in rows:
        for entry in row.get("fix_rounds_detail") or []:
            rounds += 1
            cause = str(entry.get("cause") or "other")
            causes[cause] = causes.get(cause, 0) + 1
            phase = str(entry.get("phase") or "fix")
            phases[phase] = phases.get(phase, 0) + 1
            if entry.get("changed"):
                changed_rounds += 1
    # 021 AC-7: does each verification phase catch anything?
    selfcheck_runs = [r for r in rows if r.get("self_check")]
    verifier_runs = [r for r in rows if r.get("verifier")]
    return {
        "runs": len(rows),
        "green": len(green),
        "cost_per_green_mean": (sum(costs) / len(costs)) if costs else 0.0,
        "cost_per_green_median": statistics.median(costs) if costs else 0.0,
        "cost_total_green": sum(costs),
        "fix_round_rate": (
            sum(1 for n in fix_rounds if n > 0) / len(fix_rounds) if fix_rounds else 0.0
        ),
        "duration_p50": statistics.median(durations) if durations else 0.0,
        "duration_p90": (
            sorted(durations)[max(0, int(len(durations) * 0.9) - 1)] if durations else 0.0
        ),
        "stop_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "by_role": by_role,
        "fix_causes": dict(sorted(causes.items(), key=lambda kv: -kv[1])),
        "fix_phases": dict(sorted(phases.items(), key=lambda kv: -kv[1])),
        "fix_rounds_total": rounds,
        "fix_rounds_changed": changed_rounds,
        "self_check_runs": len(selfcheck_runs),
        "self_check_hits": sum(1 for r in selfcheck_runs if (r.get("self_check") or {}).get("hit")),
        "verifier_runs": len(verifier_runs),
        "verifier_hits": sum(1 for r in verifier_runs if (r.get("verifier") or {}).get("hit")),
    }


def render(summary: dict[str, Any]) -> str:
    lines = [
        f"runs: {summary['runs']}   green: {summary['green']}",
        (
            f"cost/green: mean ${summary['cost_per_green_mean']:.4f}  "
            f"median ${summary['cost_per_green_median']:.4f}  "
            f"total ${summary['cost_total_green']:.4f}"
        ),
        (
            f"fix-round rate: {summary['fix_round_rate'] * 100:.0f}%   "
            f"duration p50 {summary['duration_p50']:.0f}s  p90 {summary['duration_p90']:.0f}s"
        ),
    ]
    if summary["stop_reasons"]:
        lines.append("stops: " + ", ".join(f"{k}={v}" for k, v in summary["stop_reasons"].items()))
    if summary.get("fix_rounds_total"):
        causes = ", ".join(f"{k}={v}" for k, v in summary["fix_causes"].items())
        phases = ", ".join(f"{k}={v}" for k, v in summary["fix_phases"].items())
        changed = summary["fix_rounds_changed"]
        total = summary["fix_rounds_total"]
        lines.append(
            f"repair rounds: {total} ({changed} changed the delta, "
            f"{total - changed} changed nothing)"
        )
        lines.append(f"  causes: {causes}")
        lines.append(f"  phases: {phases}")
    if summary.get("self_check_runs") or summary.get("verifier_runs"):
        sc = summary["self_check_runs"]
        vr = summary["verifier_runs"]
        lines.append(
            f"verification: self-check {summary['self_check_hits']}/{sc} hit, "
            f"verifier {summary['verifier_hits']}/{vr} hit"
        )
    if summary["by_role"]:
        lines.append("tokens by role:")
        for role, bucket in sorted(summary["by_role"].items()):
            lines.append(
                f"  {role:<16} prompt {int(bucket['prompt_tokens']):>9} "
                f"completion {int(bucket['completion_tokens']):>8} "
                f"${bucket['cost_usd']:.4f}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    rows = collect()
    print(render(summarize(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
