"""Why did the loop need another round? (021 T2, AC-2)

The 020 history can say *that* 59% of green runs needed a fix round and which
gate was red, but not whether the round was code work or a verdict/evidence
problem. This module labels a round mechanically, from the report the coder
received — never from model prose — so the next harness change is chosen from a
distribution instead of a feeling.

Causes, in precedence order:

    scenario  the 019 verifier blocked and its corrections drove the round
    verdict   QA produced no grounded verdict (unknown / ungrounded block)
    evidence  no gate evidence, or the round changed nothing (stale delta)
    type      a type-check gate is failing
    test      a test gate is failing (assertion/failure lines)
    lint      only lint/format gates are failing
    other     anything else

A `type` error often makes a test fail too, so type outranks test: fixing the
type is what ends the round.
"""

from __future__ import annotations

import re
from typing import Any

CAUSES = ("scenario", "verdict", "evidence", "type", "test", "lint", "other")

_TEST = ("test", "pytest", "vitest", "playwright", "jest")
_LINT = ("lint", "eslint", "prettier", "ruff", "format", "style")
_TYPE = ("check", "mypy", "tsc", "typecheck", "type-check")

_ASSERTION_RE = re.compile(
    r"assertionerror|assert |expected .* to |deeply equal|not equal|✖|failed \(|"
    r"test files|fail\s+src/|fail\s+tests/",
    re.IGNORECASE,
)


def command_kind(command: str) -> str:
    """`test` / `lint` / `type` / `other` for one gate command.

    Read the executable and, for a package manager, the script name: a
    substring test would call `mypy app tests` a test gate because of its
    arguments.
    """
    parts = (command or "").split()
    if not parts:
        return "other"
    exe = parts[0].rsplit("/", 1)[-1].lower()
    if exe in {"pytest", "vitest", "jest", "playwright"}:
        return "test"
    if exe in {"mypy", "tsc"}:
        return "type"
    if exe in {"ruff", "eslint", "prettier"}:
        return "lint"
    if exe in {"npm", "pnpm", "yarn"}:
        script = ""
        for index, part in enumerate(parts):
            if part in {"run", "run-script"} and index + 1 < len(parts):
                script = parts[index + 1]
                break
        if not script and "test" in parts:
            script = "test"
        low = script.lower()
        if "test" in low:
            return "test"
        if "lint" in low or "format" in low or "style" in low:
            return "lint"
        if "check" in low or "type" in low:
            return "type"
        return "other"
    low = (command or "").lower()
    if any(word in low for word in _TEST):
        return "test"
    if any(word in low for word in _LINT):
        return "lint"
    if any(word in low for word in _TYPE):
        return "type"
    return "other"


def failing_commands(gates: dict[str, int]) -> list[str]:
    return [command for command, code in (gates or {}).items() if int(code) != 0 and command != "scope"]


def classify(
    *,
    gates: dict[str, int] | None = None,
    report: dict[str, Any] | None = None,
    verdict: str = "",
    reason: str = "",
    missing: list[str] | None = None,
    changed: bool = True,
    verifier_blocked: bool = False,
    phase: str = "fix",
) -> dict[str, Any]:
    """Label one round; return the cause and the evidence it was based on."""
    failed = failing_commands(gates or {})
    if not changed:
        cause = "evidence"
    elif verifier_blocked:
        cause = "scenario"
    elif str(verdict or "").lower() in {"unknown", ""} and phase != "selfcheck":
        cause = "verdict"
    elif missing:
        cause = "evidence"
    elif not failed and str(verdict or "").lower() == "blocked":
        cause = "verdict"
    elif not failed and str(verdict or "").lower() == "pass":
        # QA passed but the harness's gate map is not green (incomplete/stale
        # evidence). That is not coder work: a fix round cannot create a gate
        # execution (004-T2 burned 731k tokens on this).
        cause = "evidence"
    else:
        kinds = {command_kind(command) for command in failed}
        if "type" in kinds:
            cause = "type"
        elif "test" in kinds:
            cause = "test"
        elif "lint" in kinds:
            cause = "lint"
        else:
            cause = "other"
        # A "test" gate whose only lines are type errors is a type round.
        if (
            cause == "test"
            and not _has_assertions(report, reason)
            and ("type" in kinds or _mentions_type(report, reason))
        ):
            cause = "type"
    return {
        "cause": cause,
        "phase": phase,
        "gates": failed,
        "changed": bool(changed),
        "verdict": str(verdict or ""),
    }


def _key_lines(report: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    for entry in (report or {}).get("gates") or []:
        if int(entry.get("exit") or 0) == 0:
            continue
        out.extend(str(line) for line in (entry.get("errors") or []))
        tail = str(entry.get("tail") or "")
        if tail:
            out.append(tail[-1500:])
    return out


def _has_assertions(report: dict[str, Any] | None, reason: str) -> bool:
    text = "\n".join(_key_lines(report)) + "\n" + str(reason or "")
    return bool(_ASSERTION_RE.search(text))


_TYPE_LINE_RE = re.compile(
    r"ts\(\d+\)|ts\d{4}|not assignable|cannot find name|does not exist on type|"
    r"type error|incompatible type|attr-defined|no-redef|missing positional",
    re.IGNORECASE,
)


def _mentions_type(report: dict[str, Any] | None, reason: str) -> bool:
    text = "\n".join(_key_lines(report)) + "\n" + str(reason or "")
    return bool(_TYPE_LINE_RE.search(text))
