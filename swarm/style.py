"""Deterministic style repair (016 follow-up).

A Prettier/ESLint slip is not coder work: the fix is mechanical
(`eslint --fix` + `prettier --write`). 007-T5's redo died on a Prettier-only
lint failure and 014-T8/T9/T10 lost rounds the same way. The harness runs the
configured formatter itself, re-checks the gate, and only then asks a coder
for something that actually needs thought.

The command is configuration, not a harness assumption: `SWARM_STYLE_FIX_COMMAND`
holds the project's own formatter command (this repo: `npm --prefix frontend
run lint:fix`).
"""

from __future__ import annotations

import os
import re

FIX_COMMAND_ENV = "SWARM_STYLE_FIX_COMMAND"
DISABLE_ENV = "SWARM_STYLE_FIX"

# Only formatting/lint-rule complaints: the formatter can fix these.
_PRETTIER_MARKERS = (
    "code style issues",
    "checking formatting",
    "prettier",
)
# ESLint rules that `--fix` can repair. A rule outside this set (e.g.
# `no-unused-vars`) is a code problem, not a wrap: the coder owns it.
_FIXABLE_RULES = frozenset(
    {
        "prefer-const",
        "no-extra-semi",
        "semi",
        "quotes",
        "singlequote",
        "doublequote",
        "indent",
        "comma-dangle",
        "no-trailing-spaces",
        "eol-last",
        "arrow-parens",
        "object-curly-spacing",
        "quote-props",
        "space-before-function-paren",
        "no-multiple-empty-lines",
        "padded-blocks",
    }
)
_RULE_RE = re.compile(r"@[\w@/-]+/([\w-]+)")
# Real code problems: a formatter cannot fix them, so the coder must.
_HARD_MARKERS = (
    "parsing error",
    "syntaxerror",
    "unexpected token",
    "cannot find name",
    "is not assignable to type",
    "transform failed",
    "duplicate identifier",
    "has already been declared",
)


def fix_command() -> str:
    """The configured formatter command (empty → the feature is off)."""
    return os.getenv(FIX_COMMAND_ENV, "").strip()


def enabled() -> bool:
    return os.getenv(DISABLE_ENV, "1") != "0" and bool(fix_command())


def is_style_failure(tail: str) -> bool:
    """True when the tail names only formatting/lint-rule problems.

    Prettier complaints are always fixable; ESLint complaints only when every
    rule they mention is one `eslint --fix` repairs.
    """
    text = tail or ""
    low = text.lower()
    if any(marker in low for marker in _HARD_MARKERS):
        return False
    if any(marker in low for marker in _PRETTIER_MARKERS):
        return True
    rules = {match.group(1).lower() for match in _RULE_RE.finditer(text)}
    if not rules:
        return False
    return all(rule in _FIXABLE_RULES for rule in rules)


def style_gate(gates: dict[str, int], tails: dict[str, str]) -> str | None:
    """The gate command that failed for style reasons only, else ``None``.

    Only when it is the *only* failing gate: if a type-check or a test gate is
    red as well, formatting is not the problem and the coder must fix the code.
    """
    failing = [cmd for cmd, code in gates.items() if int(code) != 0 and cmd != "scope"]
    if len(failing) != 1:
        return None
    command = failing[0]
    if not any(word in command for word in ("lint", "prettier", "format")):
        return None
    if not is_style_failure(tails.get(command, "")):
        return None
    return command


def style_failures(gates: dict[str, int], tails: dict[str, str]) -> list[str]:
    """Every failing command whose output names nothing but formatting.

    Unlike `style_gate` this does not require the failure to be the only one:
    the pre-QA self-check (017) formats first and then reports what is left,
    so a Prettier slip never reaches the coder as "your code is wrong".
    """
    return [
        command
        for command, code in gates.items()
        if int(code) != 0
        and command != "scope"
        and any(word in command for word in ("lint", "prettier", "format"))
        and is_style_failure(tails.get(command, ""))
    ]
