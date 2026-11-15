"""Deterministic anti-weakening guard for e2e repairs (027 T5, AC-5).

A model that can rewrite the oracle can make anything green: delete the test,
mark it `skip`, or drop the assertion that fails. The market learned this the
hard way (Donobu flags "any change that weakens a test"; Uber's AutoCover
reverts "do no harm" patches) and so did we — 010-T4 was green having touched
only `helpers.ts`.

This module is the check that no prompt can talk past. It compares the spec
files before and after a repair:

* a test title that existed before must still exist;
* no `test.skip(`, `test.fixme(` or `.only(` may be *added*;
* the number of `expect(` assertions per file may not decrease.

The final proof is separate (AC-6): the failing titles must appear *and pass*
in a recorded full suite at the current delta hash.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

TEST_TITLE = re.compile(r"""\btest(?:\.\w+)?\(\s*['"`](?P<title>[^'"`]+)['"`]""")
ASSERTION = re.compile(r"\bexpect\s*\(")
DISABLED = re.compile(r"\b(?:test\.skip|test\.fixme|test\.only|describe\.skip|\.only)\s*\(")


def spec_facts(text: str) -> dict[str, Any]:
    """What a spec file asserts, in a form that can be compared."""
    return {
        "titles": sorted({m.group("title") for m in TEST_TITLE.finditer(text)}),
        "assertions": len(ASSERTION.findall(text)),
        "disabled": sorted({m.group(0).split(".")[-1].split("(")[0] for m in DISABLED.finditer(text)}),
    }


def facts_for(root: Path, files: list[str]) -> dict[str, dict[str, Any]]:
    """Facts per file, skipping anything that is not a readable spec."""
    out: dict[str, dict[str, Any]] = {}
    for name in files:
        path = Path(root) / name
        try:
            out[name] = spec_facts(path.read_text())
        except OSError:
            continue
    return out


def weakened(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> list[str]:
    """Reasons a repair weakened the suite; empty means it did not."""
    problems: list[str] = []
    for name, old in before.items():
        new = after.get(name)
        if new is None:
            problems.append(f"{name}: the spec file disappeared")
            continue
        removed = [title for title in old.get("titles", []) if title not in new.get("titles", [])]
        if removed:
            problems.append(f"{name}: removed test(s): {', '.join(removed)}")
        added = sorted(set(new.get("disabled", [])) - set(old.get("disabled", [])))
        if added:
            problems.append(f"{name}: added {', '.join(added)}")
        if int(new.get("assertions", 0)) < int(old.get("assertions", 0)):
            problems.append(
                f"{name}: assertions dropped {old.get('assertions')} -> {new.get('assertions')}"
            )
    return problems


def weaken_reason(problems: list[str]) -> str:
    """One line for `run.json` / `human_log.txt`."""
    return "e2e repair weakened the suite: " + "; ".join(problems)


def e2e_files(root: Path) -> list[str]:
    """Every spec file the suite runs (repo-relative), for baseline capture."""
    base = Path(root) / "frontend" / "e2e"
    if not base.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in base.rglob("*.ts")
        if path.is_file()
    )
