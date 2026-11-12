"""Harness-owned evidence (015): shell log, gate evidence, QA report, failure signatures.

The point of this module: the *agent* decides to run a gate, but the *harness*
records the real exit code. Green is derived from those records, never from
model prose, so removing the flow's own gate execution does not weaken 012 AC-4.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SHELL_LOG = "shell_log.jsonl"
DEFAULT_AGENT = "QA Gatekeeper"
# What the harness keeps of one gate execution. It is the source the report's
# key lines are extracted from, so it must be big enough to hold the failure
# header and the summary; it is disk, not prompt (020 T4 spills the prompt side).
TAIL_CHARS = int(os.getenv("SWARM_GATE_TAIL_CHARS", "20000"))
REPORT_TAIL_CHARS = 4000
# A fix round is a prompt, not a log: the failing gate output has to reach the
# coder intact. 007-T9 (2026-11-10) lost its vitest failure text to the 9000
# char report cap, so the coder "fixed" a file it could not see.
FAILURE_TAIL_CHARS = 3000
REPORT_MAX_CHARS = 14000
MAX_KEY_LINES = 40


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
    """Comprehensive, bounded report the coder can investigate from.

    Failing gates come first and carry a compact list of *key lines*
    (`file:line: message`), because the raw tail of `svelte-check` or
    `vitest` is too noisy to act on — and too long to survive a prompt.
    """
    full_by_command: dict[str, str] = {}
    for block in tails:
        head, _, body = block.partition("\n")
        command = head.removeprefix("$ ").strip()
        if command:
            full_by_command[command] = body
    entries = []
    for command, code in gates.items():
        full = full_by_command.get(command, "")
        entries.append(
            {
                "command": command,
                "exit": int(code),
                # The prompt copy is bounded; the key lines are read from the
                # whole recorded tail so a failure header is not cut away.
                "tail": full[-REPORT_TAIL_CHARS:],
                "errors": extract_error_lines(full),
            }
        )
    entries.sort(key=lambda e: (int(e["exit"]) == 0, e["command"]))
    return {
        "version": 2,
        "verdict": verdict,
        "reason": (reason or "")[-1500:],
        "changed_files": list(changed),
        "missing": list(missing),
        "gates": entries,
    }


def _compaction_on() -> bool:
    from swarm.compaction import enabled

    return enabled()


def report_text(report: dict[str, Any]) -> str:
    """Render the report for a prompt (bounded, failures first).

    007-T9 (2026-11-10): the old render put every gate in config order and
    cut the text at 9000 chars, so the vitest failure never reached the coder
    — five fix rounds were spent guessing. Now the failing gates lead, each
    with its key lines, and the budget covers the failure output.
    """
    lines = [
        f"QA verdict: {report.get('verdict') or 'unknown'}",
        f"QA reason: {report.get('reason') or '(none)'}",
        f"Changed files: {', '.join(report.get('changed_files') or []) or '(none)'}",
    ]
    if report.get("missing"):
        lines.append("Gates QA did not run: " + ", ".join(report["missing"]))
    entries = list(report.get("gates") or [])
    failing = [e for e in entries if int(e.get("exit") or 0) != 0]
    passing = [e for e in entries if int(e.get("exit") or 0) == 0]
    if failing:
        lines.append("\nFAILING GATES (fix these first):")
    for entry in failing:
        lines.append(f"\n$ {entry.get('command')}  (exit={entry.get('exit')})")
        errors = list(entry.get("errors") or [])
        if errors:
            lines.append("key lines:")
            lines.extend(f"  - {line}" for line in errors)
        if entry.get("log_path"):
            # 020 AC-3: the long tail was spilled to a file; the key lines above
            # are the actionable part, and the path is there when they are not.
            lines.append(f"full log: {entry['log_path']}")
        body = str(entry.get("tail") or "")
        if body and (not errors or not _compaction_on()):
            # 020 AC-5: never send the same failure twice. Key lines are the
            # actionable form; the raw body is the fallback when extraction
            # found nothing (a formatter or an unrecognised tool's output) and
            # when context compaction is switched off (AC-3's old behaviour).
            lines.append("output:")
            lines.append(body[-FAILURE_TAIL_CHARS:])
    if passing:
        lines.append(
            "\nPASSED GATES: " + ", ".join(f"{e.get('command')} (exit=0)" for e in passing)
        )
    return "\n".join(lines)[:REPORT_MAX_CHARS]


_KEY_LINE_RE = re.compile(
    r"error|err!|ts\d{4}|parsing error|cannot find|not assignable|assertionerror|"
    r"referenceerror|typeerror|syntaxerror|unexpected|✖|fail|warning",
    re.IGNORECASE,
)
_PATH_LINE_RE = re.compile(
    r"^(?P<path>[\w.\-/\\ ]*?[\w-]+\.(?:ts|tsx|js|mjs|svelte|py|css|json))"
    r"(?::(?P<line>\d+))?(?::(?P<col>\d+))?\s*$"
)
_NOISE = (
    "checking formatting",
    "npm notice",
    "> frontend@",
    "> swarm@",
    "run lint",
    "run check",
    "eslint .",
    "prettier --check",
    "start at ",
    "duration ",
    "test files",
    "pass with no tests",
)
_SUMMARY_RE = re.compile(r"(\bfound \d+|\d+\s+(errors?|problems?|warnings?)\b|✖\s*\d+)", re.IGNORECASE)
_ABS_PATH_RE = re.compile(r"(?<![\w.])/(?:[\w.\-]+/)+([\w-]+\.[A-Za-z]{1,5})")


def _short_path(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def extract_error_lines(text: str, limit: int = MAX_KEY_LINES) -> list[str]:
    """The lines that name a problem, as `file:line: message`.

    A raw gate tail is unusable in a prompt: `svelte-check` prints 27 errors
    with absolute paths and a stack of context lines. The coder needs the
    short list of `file:line: message` lines, and the file that a bare
    message belongs to (`Error: Cannot find name 'positionStore'` follows a
    path line that carries the position).
    """
    out: list[str] = []
    seen: set[str] = set()
    current_file = ""
    current_line = ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        path_match = _PATH_LINE_RE.match(line)
        if path_match:
            current_file = _short_path(path_match.group("path"))
            current_line = path_match.group("line") or ""
            continue
        if len(line) > 400:
            continue
        low = line.lower()
        if any(noise in low for noise in _NOISE):
            continue
        if _SUMMARY_RE.search(line) and "error:" not in low:
            continue
        if not _KEY_LINE_RE.search(line):
            continue
        message = re.sub(r"\s+", " ", line)
        message = _ABS_PATH_RE.sub(r"\1", message)
        if current_file and not re.search(r"[\w-]+\.\w{1,5}:\d+", message):
            prefix = f"{current_file}:{current_line}" if current_line else current_file
            message = f"{prefix} {message}"
            current_line = ""
        if message in seen:
            continue
        seen.add(message)
        out.append(message)
        if len(out) >= limit:
            break
    return out


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
