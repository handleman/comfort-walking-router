"""Pre-QA static verification (017).

A red type check or a red linter is a mechanical defect, not a design
question: 007-T9 (2026-11-11) handed QA a test that called `tick()` on a
`PositionProvider`, and the run spent three QA rounds and two coder rounds
(one of them on a fix that changed no file) on a single line the type checker
had already named. The coder must not pass work on with a red type check.

The harness runs the project's *static* checks — type checker and linter, not
the test suites — right after the micro-steps. When they are red the coder
gets the evidence (`file:line: message`) and fixes the cause before QA is
ever asked to review.

The commands are configuration, not a harness assumption:
`SWARM_SELF_CHECK_COMMANDS` holds the project's own commands; without it the
static subset of `SWARM_GATE_COMMANDS` is used. `SWARM_SELF_CHECK=0`
disables the phase.

The self-check is *not* a gate: it never makes a run green. Green comes from
QA's own recorded executions (`swarm/evidence.py`), and the self-check runs
under its own agent role, so its records are never counted as QA evidence.
"""

from __future__ import annotations

import os
import re
import shlex
from collections.abc import Mapping

COMMANDS_ENV = "SWARM_SELF_CHECK_COMMANDS"
DISABLE_ENV = "SWARM_SELF_CHECK"

# Binaries that type-check or lint.
_STATIC_BINARIES = frozenset(
    {
        "ruff",
        "mypy",
        "pyright",
        "pyre",
        "tsc",
        "eslint",
        "prettier",
        "svelte-check",
        "flake8",
        "pylint",
        "biome",
    }
)
# npm script names that are checks (not tests, not builds).
_STATIC_SCRIPTS = frozenset({"check", "lint", "typecheck", "type-check", "lint:types"})
# make targets that are checks.
_STATIC_TARGETS = frozenset({"check", "lint", "typecheck", "type-check"})

# Bounds for the report the coder receives.
MAX_REPORT_CHARS = 8000
MAX_KEY_LINES = 20
TAIL_CHARS = 2000


def enabled(env: Mapping[str, str] | None = None) -> bool:
    """True unless the phase is switched off."""
    source: Mapping[str, str] = os.environ if env is None else env
    return source.get(DISABLE_ENV, "1") != "0"


def is_static_check(command: str) -> bool:
    """True when the command type-checks or lints (never a test suite).

    The classification is a heuristic over the command line — the project
    stays configurable through `SWARM_SELF_CHECK_COMMANDS`.
    """
    try:
        argv = shlex.split(command or "")
    except ValueError:
        return False
    if not argv:
        return False
    if argv[0] in _STATIC_BINARIES:
        return True
    if argv[0] == "npm":
        if "run" not in argv:
            return False
        index = argv.index("run") + 1
        return index < len(argv) and argv[index] in _STATIC_SCRIPTS
    if argv[0] == "make":
        return len(argv) > 1 and argv[1] in _STATIC_TARGETS
    return False


def commands(gates: list[str], env: Mapping[str, str] | None = None) -> list[str]:
    """The commands to run before QA.

    `SWARM_SELF_CHECK_COMMANDS` wins; otherwise the static subset of the
    project's gate commands is used (types + lint, never the test suites).
    """
    source: Mapping[str, str] = os.environ if env is None else env
    raw = source.get(COMMANDS_ENV, "").strip()
    if raw:
        return [c.strip() for c in re.split(r"[;\n]", raw) if c.strip()]
    return [command for command in gates if is_static_check(command)]


def render_report(
    codes: dict[str, int],
    tails: dict[str, str],
    changed: list[str] | None = None,
) -> str:
    """A bounded, actionable report: the failing command and its key lines.

    The same shape as the QA report (failing first, `file:line: message`
    key lines, raw output below), because it feeds the same kind of coder
    fix round.
    """
    from swarm.evidence import extract_error_lines

    lines: list[str] = ["STATIC CHECKS FAILED (fix these before QA):"]
    if changed:
        lines.append("Changed files: " + ", ".join(changed))
    failing = [cmd for cmd, code in codes.items() if int(code) != 0]
    passing = [cmd for cmd, code in codes.items() if int(code) == 0]
    for command in failing:
        body = tails.get(command, "")
        lines.append(f"\n$ {command}  (exit={codes[command]})")
        key_lines = extract_error_lines(body, limit=MAX_KEY_LINES)
        if key_lines:
            lines.append("key lines:")
            lines.extend(f"  - {line}" for line in key_lines)
        if body:
            lines.append("output:")
            lines.append(body[-TAIL_CHARS:])
    if passing:
        lines.append("\nGREEN CHECKS: " + ", ".join(f"{cmd} (exit=0)" for cmd in passing))
    return "\n".join(lines)[:MAX_REPORT_CHARS]
