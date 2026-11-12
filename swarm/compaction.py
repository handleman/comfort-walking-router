"""Context compaction and tool-result spilling (020 T4, AC-3).

A fix round re-sends the whole conversation context: the concatenation of every
micro-step output, plus the QA report with up to 4k chars of tail per failing
gate. Both grow with the round number, so the most expensive rounds are the
ones that already failed once. Two rules keep the prompt flat:

1. **Step outputs become a digest.** The coder's own step outputs are written to
   `<run>/step_outputs/step-NNN.txt` in full; the prompt gets one line per step:
   index, files touched, the one-line outcome and the path to the rest.
2. **A long failing gate tail is spilled.** Above `SWARM_GATE_SPILL_CHARS`
   (default 2000) the body is written to `<run>/gate_logs/<gate>.log`, and the
   report keeps the extracted `file:line: message` key lines plus the log path.

The information a fix round needs is preserved: which step, which file, which
error line, and where the rest is. `SWARM_CONTEXT_COMPACT=0` restores the 019
behaviour exactly (full concatenation, tails in the report).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

STEPS_DIR = "step_outputs"
GATE_DIR = "gate_logs"
# The QA transcript already caps a gate tail at 4000 chars (evidence.TAIL_CHARS),
# so a 4000-char spill threshold could never fire. 2000 is the point where the
# raw output stops being useful in a prompt and starts being a log file.
DEFAULT_SPILL_CHARS = 2000
STEP_HEADER_RE = re.compile(r"^---\s*step\s*(\d+)\s*/\s*(\d+)\s*---\s*\n?", re.MULTILINE)
_PATH_RE = re.compile(r"(?:app|tests|frontend|contracts|docs|swarm)/[\w./-]+\.[A-Za-z0-9]+")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def enabled(env: dict[str, str] | None = None) -> bool:
    """`SWARM_CONTEXT_COMPACT=0` turns compaction and spilling off (019 behaviour)."""
    source = os.environ if env is None else env
    return str(source.get("SWARM_CONTEXT_COMPACT", "1")).strip().lower() not in {"0", "false", "no"}


def spill_chars(env: dict[str, str] | None = None) -> int:
    source = os.environ if env is None else env
    try:
        return max(0, int(source.get("SWARM_GATE_SPILL_CHARS", DEFAULT_SPILL_CHARS)))
    except (TypeError, ValueError):
        return DEFAULT_SPILL_CHARS


def _one_line(text: str, limit: int = 160) -> str:
    for raw in (text or "").splitlines():
        line = " ".join(raw.strip().split())
        if line and not line.startswith(("#", "---")):
            return line[:limit]
    return "(no output)"


def _files(text: str, limit: int = 3) -> list[str]:
    out: list[str] = []
    for match in _PATH_RE.finditer(text or ""):
        path = match.group(0).rstrip(".,;:")
        if path not in out:
            out.append(path)
        if len(out) >= limit:
            break
    return out


def step_digest_line(index: int, total: int, output: str, rel_path: str) -> str:
    """One line per step: index, files, outcome, and the path to the full text."""
    body = STEP_HEADER_RE.sub("", output).strip()
    files = _files(body)
    where = f" [{', '.join(files)}]" if files else ""
    return f"--- step {index}/{total} ---{where} {_one_line(body)} (full: {rel_path})"


def compact_steps(
    outputs: list[str],
    run_dir: Path,
    *,
    enabled_flag: bool | None = None,
) -> tuple[str, dict[str, Any]]:
    """Write full step outputs to disk; return (prompt digest, record).

    The digest is deterministic for the same outputs: a resumed run rewrites the
    same files with the same content and gets the same text.
    """
    on = enabled() if enabled_flag is None else enabled_flag
    if not on:
        text = "\n".join(outputs)
        return text, {"enabled": False, "mode": "full", "chars": len(text)}

    out_dir = Path(run_dir) / STEPS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    total = len(outputs)
    for i, output in enumerate(outputs, 1):
        match = STEP_HEADER_RE.search(output or "")
        total = int(match.group(2)) if match else total
        name = f"step-{i:03d}.txt"
        (out_dir / name).write_text(output or "", encoding="utf-8")
        lines.append(step_digest_line(i, total, output or "", f"{STEPS_DIR}/{name}"))
    digest = "\n".join(lines)
    full_chars = sum(len(o) for o in outputs)
    return digest, {
        "enabled": True,
        "mode": "digest",
        "steps_spilled": len(outputs),
        "dir": STEPS_DIR,
        "full_step_chars": full_chars,
        "digest_chars": len(digest),
        "chars_saved": max(0, full_chars - len(digest)),
    }


def _slug(command: str) -> str:
    base = _SLUG_RE.sub("-", (command or "gate").lower()).strip("-")
    return (base or "gate")[:60]


def spill_report(
    report: dict[str, Any],
    run_dir: Path,
    *,
    max_chars: int | None = None,
    enabled_flag: bool | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Move long failing-gate tails out of the report, keeping key lines + path.

    The report object is mutated in place (it is the run's own evidence) and
    returned, together with the compaction record. Gates that pass are already
    rendered as one line, so only a failing tail can be long.
    """
    on = enabled() if enabled_flag is None else enabled_flag
    limit = spill_chars() if max_chars is None else max_chars
    if not on:
        return report, {"enabled": False, "gate_logs": []}

    out_dir = Path(run_dir) / GATE_DIR
    logs: list[dict[str, Any]] = []
    saved = 0
    used: set[str] = set()
    for entry in report.get("gates") or []:
        try:
            failing = int(entry.get("exit") or 0) != 0
        except (TypeError, ValueError):
            failing = False
        body = str(entry.get("tail") or "")
        if not failing or len(body) <= limit:
            continue
        name = _slug(str(entry.get("command") or "gate"))
        if name in used:
            name = f"{name}-{len(used) + 1}"
        used.add(name)
        rel = f"{GATE_DIR}/{name}.log"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = Path(run_dir) / rel
        path.write_text(body, encoding="utf-8")
        entry["tail"] = ""
        entry["log_path"] = rel
        saved += len(body)
        logs.append({"command": entry.get("command"), "path": rel, "chars": len(body)})
    report["spilled"] = bool(logs)
    return report, {
        "enabled": True,
        "threshold": limit,
        "gate_logs": logs,
        "gate_chars_saved": saved,
        "dir": GATE_DIR,
    }


def merge_records(*records: dict[str, Any]) -> dict[str, Any]:
    """Combine step and gate records into one `run.json.compaction` object."""
    out: dict[str, Any] = {}
    logs: list[dict[str, Any]] = []
    for record in records:
        for key, value in record.items():
            if key == "gate_logs":
                logs.extend(value or [])
            elif key in {"chars_saved", "gate_chars_saved"}:
                out[key] = int(out.get(key, 0)) + int(value or 0)
            elif key not in out:
                out[key] = value
    if logs:
        out["gate_logs"] = logs
    out["enabled"] = bool(out.get("enabled", False))
    return out
