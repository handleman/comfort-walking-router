"""Harness-owned evidence (015): shell log, gate evidence, QA report, failure signatures.

The point of this module: the *agent* decides to run a gate, but the *harness*
records the real exit code. Green is derived from those records, never from
model prose, so removing the flow's own gate execution does not weaken 012 AC-4.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SHELL_LOG = "shell_log.jsonl"
DEFAULT_AGENT = "QA Gatekeeper"
TAIL_CHARS = 4000
REPORT_TAIL_CHARS = 6000


def append_execution(
    log_path: Path,
    *,
    agent: str,
    argv: list[str],
    exit_code: int,
    duration_ms: int,
    changed_after: str,
    tail: str,
) -> None:
    """Append one execution record. Never raises: logging must not break a command."""
    record = {
        "agent": agent,
        "argv": list(argv),
        "exit": int(exit_code),
        "duration_ms": int(duration_ms),
        "changed_after": changed_after,
        "tail": (tail or "")[-TAIL_CHARS:],
        "at": _now(),
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        pass


def read_executions(log_path: Path) -> list[dict[str, Any]]:
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def gate_evidence(
    *,
    executions: Iterable[dict[str, Any]],
    commands: Iterable[str],
    current_hash: str,
    agent: str | None = DEFAULT_AGENT,
    agents: Iterable[str] | None = None,
) -> tuple[dict[str, int], list[str], list[str]]:
    """Return (gates, tails, missing) from harness-recorded QA executions.

    A command counts only when its newest record comes from the QA agent at the
    *current* in-scope content hash, i.e. the gate ran after the last edit.
    """
    allowed = {agent} if agents is None else set(agents)
    latest: dict[str, dict[str, Any]] = {}
    for rec in executions:
        if str(rec.get("agent") or "") not in allowed:
            continue
        if str(rec.get("changed_after") or "") != current_hash:
            continue
        argv = rec.get("argv") or []
        try:
            key = " ".join(str(a) for a in argv)
        except TypeError:
            continue
        latest[key] = rec
    gates: dict[str, int] = {}
    tails: list[str] = []
    missing: list[str] = []
    for command in commands:
        norm = " ".join(command.split())
        rec = latest.get(norm) or latest.get(command)
        if rec is None:
            missing.append(command)
            continue
        try:
            code = int(rec.get("exit"))
        except (TypeError, ValueError):
            code = 99
        gates[command] = code
        body = str(rec.get("tail") or "")
        tails.append(f"$ {command}\nexit={code}\n{body}")
    return gates, tails, missing


def qa_report(
    *,
    gates: dict[str, int],
    tails: Iterable[str],
    changed: Iterable[str],
    verdict: str,
    reason: str,
    missing: Iterable[str] = (),
) -> dict[str, Any]:
    """Comprehensive, bounded report the coder can investigate from."""
    tail_by_command: dict[str, str] = {}
    for block in tails:
        head, _, body = block.partition("\n")
        command = head.removeprefix("$ ").strip()
        if command:
            tail_by_command[command] = body[-REPORT_TAIL_CHARS:]
    entries = [
        {
            "command": command,
            "exit": int(code),
            "tail": tail_by_command.get(command, "")[-REPORT_TAIL_CHARS:],
        }
        for command, code in gates.items()
    ]
    return {
        "verdict": verdict,
        "reason": (reason or "")[-1500:],
        "changed_files": list(changed),
        "missing": list(missing),
        "gates": entries,
    }


def report_text(report: dict[str, Any]) -> str:
    """Render the report for a prompt (bounded)."""
    lines = [
        f"QA verdict: {report.get('verdict') or 'unknown'}",
        f"QA reason: {report.get('reason') or '(none)'}",
        f"Changed files: {', '.join(report.get('changed_files') or []) or '(none)'}",
    ]
    if report.get("missing"):
        lines.append("Gates QA did not run: " + ", ".join(report["missing"]))
    for entry in report.get("gates") or []:
        lines.append(f"\n$ {entry.get('command')}  (exit={entry.get('exit')})")
        body = str(entry.get("tail") or "")
        if body:
            lines.append(body[-REPORT_TAIL_CHARS:])
    return "\n".join(lines)[:12000]


def split_tails(transcript: str) -> list[str]:
    """Split a transcript into `$ command` blocks for `qa_report`."""
    blocks: list[str] = []
    current: str | None = None
    for line in (transcript or "").splitlines():
        if line.startswith("$ "):
            if current is not None:
                blocks.append(current)
            current = line
        elif current is not None:
            current += "\n" + line
    if current is not None:
        blocks.append(current)
    return blocks


def signature(step: str, error: str) -> str:
    """Normalized failure signature: same step + same kind of error → same key."""
    text = (error or "").lower()
    text = re.sub(r"/[^\s:]+/([\w.-]+)", r"\1", text)  # absolute paths → basename
    text = re.sub(r"\b\d+\b", "N", text)
    text = re.sub(r"\s+", " ", text).strip()
    digest = hashlib.sha256(f"{step}\x00{text[:400]}".encode()).hexdigest()
    return digest[:16]


def count_skipped(transcript: str) -> int:
    """Sum `N skipped` counts from gate output."""
    return sum(int(n) for n in re.findall(r"(\d+)\s+skipped", transcript or ""))


def _now() -> str:
    import datetime as dt

    return dt.datetime.now().isoformat(timespec="seconds")
