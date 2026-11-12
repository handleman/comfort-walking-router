"""Human-readable run report, written next to the run (018).

The dashboard can *show* a report (`h`), but a terminal screen is not
copy-pasteable: the operator cannot select it, pipe it, or attach it to an
issue. This module renders the same report to a plain-text file next to the
run's `run.json`, so the answer to "why did this stop?" is a file you can
`cat`, `grep`, paste into a ticket, or read on a phone.

Dependency-free (no textual, no crewai): the harness writes the report on
every run, including headless ones, and `make swarm-log` prints it without a
TUI. `swarm.tui` imports the renderer from here, so the screen and the file
can never drift apart.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "swarm" / "runs"
REPORT_NAME = "human_log.txt"
MAX_EVENTS = 80
MAX_TAIL = 2500


# ---- formatting helpers (shared with the dashboard) ----


def fmt_tokens(n: int | None) -> str:
    if not n:
        return "0"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def fmt_cost(cost: float | None) -> str:
    if cost is None:
        return "unknown"
    if cost == 0:
        return "$0"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def _read_events(run_dir: Path, limit: int = MAX_EVENTS) -> list[dict[str, Any]]:
    fp = run_dir / "events.jsonl"
    try:
        lines = fp.read_text(errors="replace").splitlines()[-limit:]
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    return events


def format_human_report(
    payload: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    run_name: str = "",
    event_limit: int = MAX_EVENTS,
) -> str:
    """Plain-text 'why did this run stop?' report."""
    p = payload or {}
    spec, task = p.get("spec", "?"), p.get("task", "?")
    status = p.get("status", "?")
    lines = [f"{spec} {task} — {status}" + (f"  ({run_name})" if run_name else "")]
    usage = p.get("usage") or {}
    bits: list[str] = []
    if usage.get("total_tokens"):
        bits.append(f"tok {fmt_tokens(usage.get('total_tokens'))}")
    if usage.get("cost_usd") is not None:
        bits.append(f"cost {fmt_cost(usage.get('cost_usd'))}")
    if usage.get("duration_seconds") is not None:
        bits.append(f"time {fmt_duration(usage.get('duration_seconds'))}")
    if bits:
        lines.append("  ".join(bits))
    if p.get("reason_code"):
        lines.append(f"reason_code: {p['reason_code']}")

    lines += ["", "why"]
    reasons: list[str] = []
    verdict = str(p.get("review_verdict") or "")
    if verdict and verdict != "pass":
        reasons.append(f"reviewer verdict: {verdict} (PASS required)")
    for key, label in (
        ("review_note", "reviewer"),
        ("vacancy_note", "vacancy"),
        ("budget_note", "budget"),
        ("quota_note", "quota"),
        ("recovery_note", "recovery"),
        ("approval_error", "approval"),
        ("evidence_note", "QA evidence"),
        ("verification_note", "verification"),
    ):
        value = p.get(key)
        if value:
            reasons.append(f"{label}: {value}")
    self_check = p.get("self_check") or {}
    if self_check.get("red"):
        reasons.append(
            "self-check red: " + ", ".join(str(command) for command in self_check["red"])
        )
    verifier = p.get("verifier") or {}
    if verifier.get("blocked"):
        count = len(verifier.get("findings") or [])
        reasons.append(f"scenario verifier: BLOCKED ({count} finding(s)) — needs a human")
    if not reasons:
        if status == "needs_human":
            reasons.append("no explicit note — inspect gates/reviewer below")
        elif status == "green":
            reasons.append("all gates 0 + reviewer PASS + committed")
    lines += [f"  - {reason}" for reason in reasons]

    gates = p.get("gates") or {}
    if gates:
        lines += ["", "gates"]
        lines += [f"  {'✓' if code == 0 else '✗'} {name} {code}" for name, code in gates.items()]

    qa = p.get("qa_report") or {}
    if qa.get("gates"):
        lines += ["", f"QA report ({qa.get('verdict') or '?'})"]
        for gate in qa["gates"][:8]:
            lines.append(
                f"  {'✓' if gate.get('exit') == 0 else '✗'} {gate.get('command')} {gate.get('exit')}"
            )
            for key_line in (gate.get("errors") or [])[:12]:
                lines.append(f"      {key_line}")

    verifier = p.get("verifier") or {}
    if verifier.get("verdict"):
        mark = str(verifier.get("verdict")).upper()
        lines += [
            "",
            (
                f"verifier ({mark}, round {verifier.get('rounds', 0)}, "
                f"model {verifier.get('model') or '?'})"
            ),
        ]
        for finding in (verifier.get("findings") or [])[:12]:
            lines.append(f"  ✗ {finding}")
        for step in (verifier.get("plan") or [])[:8]:
            lines.append(f"  → {step}")
        not_read = verifier.get("skipped") or []
        if not_read:
            lines.append(
                "  not read: "
                + ", ".join(f"{item.get('path')} ({item.get('chars', 0)} chars)" for item in not_read[:8])
            )

    steps = p.get("steps") or []
    if steps:
        lines += ["", "steps"] + [
            f"  {step.get('index')}. {step.get('model')} ({step.get('routing_reason')})"
            for step in steps[:12]
        ]

    for key, label in (
        ("skipped_ac", "unverified ACs"),
        ("stashed", "stashed"),
        ("out_of_scope_reverted", "reverted"),
    ):
        if p.get(key):
            lines.append(f"  {label}: {', '.join(str(v) for v in p[key])}")

    by_role = (p.get("usage") or {}).get("by_role") or {}
    if by_role:
        lines += ["", "cost by role"] + [
            f"  {role:<16} {fmt_tokens(usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0)):>8}"
            f" {fmt_cost(usage.get('cost_usd'))}"
            for role, usage in sorted(by_role.items())
        ]

    changed = p.get("changed_files") or []
    if changed:
        lines += ["", "changed"] + [f"  {path}" for path in changed[:20]]

    review = str(p.get("review_tail") or "").strip()
    if review:
        lines += ["", "reviewer output", review[-MAX_TAIL:]]
    transcript = str(p.get("gate_transcript_tail") or "").strip()
    if transcript:
        lines += ["", "gate transcript", transcript[-MAX_TAIL:]]
    result = str(p.get("result_tail") or "").strip()
    if result and not review:
        lines += ["", "last output", result[-MAX_TAIL:]]

    if events:
        lines += ["", f"events (last {min(len(events), event_limit)})"]
        for ev in events[-event_limit:]:
            etype = str(ev.get("type", "?"))
            if etype == "chunk":
                continue
            agent = str(ev.get("agent", ""))
            text = " ".join(str(ev.get("text", "")).split())[:240]
            lines.append(f"  {etype:<14} {agent:<16} {text}".rstrip())
    return "\n".join(lines)


def write_human_report(run_dir: Path) -> Path | None:
    """Write `<run_dir>/human_log.txt`; returns the path, or None on failure."""
    try:
        payload = json.loads((run_dir / "run.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    report = format_human_report(payload, _read_events(run_dir), run_name=run_dir.name)
    try:
        path = run_dir / REPORT_NAME
        path.write_text(report + "\n")
    except OSError:
        return None
    return path


def latest_run_dir(runs_dir: Path | None = None) -> Path | None:
    """Newest run directory (by name), or None."""
    base = runs_dir or RUNS_DIR
    if not base.is_dir():
        return None
    dirs = sorted(
        (p for p in base.iterdir() if p.is_dir() and p.name[:1].isdigit()),
        reverse=True,
    )
    return dirs[0] if dirs else None


def main(argv: list[str] | None = None) -> int:
    """Print the human-readable report for a run (default: the newest one)."""
    import argparse

    ap = argparse.ArgumentParser(description="Human-readable swarm run report")
    ap.add_argument("run", nargs="?", default=None, help="run dir name or path")
    args = ap.parse_args(argv)

    if args.run:
        candidate = Path(args.run)
        run_dir = candidate if candidate.is_dir() else RUNS_DIR / candidate
    else:
        run_dir = latest_run_dir()
    if run_dir is None or not run_dir.is_dir():
        print("no swarm run found; start one with `make swarm-run`")
        return 1
    try:
        payload = json.loads((run_dir / "run.json").read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"cannot read {run_dir / 'run.json'}: {e}")
        return 1
    print(format_human_report(payload, _read_events(run_dir), run_name=run_dir.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
