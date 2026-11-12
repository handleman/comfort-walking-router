"""Deterministic "is the artifact complete?" check (021 T10).

The 021 baseline replay produced the same failure three times: the coder wrote a
truncated test file (a partial `def`, no test functions), the 017 static checks
were green once the truncation parsed, and the 019 verifier spent a round to say
"this file contains no tests". That is a deterministic defect and the harness can
name it for free, before either model runs.

Only shapes a parser can decide are checked here:

- a changed `.py` file must parse (`ast.parse`);
- a changed Python test file must contain at least one test function;
- a changed frontend test file must contain a test case.

Anything semantic stays with QA and the verifier.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

TEST_MARKERS = ("/tests/", "tests/", "/test_", "test_", "/e2e/", "e2e/", ".test.", ".spec.", "_test.")
_JS_TEST_CALL = ("it(", "test(", "it.each(", "test.each(", "describe(")


def is_test_file(path: str) -> bool:
    norm = "/" + str(path).replace("\\", "/").lstrip("./")
    return any(marker in norm for marker in TEST_MARKERS)


_STEP_TARGET_RE = re.compile(
    r"(?:^|[\s:])((?:app|tests|frontend|contracts|docs|swarm)/[\w./-]+\.[A-Za-z0-9]+)"
)


def step_target(step: str) -> str | None:
    """The file a `STEP n: <file> — <action>` line targets (first repo path)."""
    match = _STEP_TARGET_RE.search(str(step or ""))
    return match.group(1) if match else None


def step_landed(target: str, changed: list[str]) -> bool:
    """True when the step actually touched the file it names.

    A plan step is an edit, not a description: a coder that pastes the new file
    into its answer and never calls Repo Create has not done the step (021 T12).
    """
    norm = str(target).replace("\\", "/").lstrip("./")
    return any(str(path).replace("\\", "/").lstrip("./") == norm for path in changed)


def incomplete(changed: list[str], root: Path) -> list[str]:
    """Problems a parser can prove; empty when every changed file looks whole."""
    problems: list[str] = []
    for raw in changed or []:
        path = str(raw)
        target = Path(root) / path
        try:
            text = target.read_text(errors="ignore")
        except OSError:
            continue
        if path.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                problems.append(f"{path}: does not parse ({exc.msg} at line {exc.lineno})")
                continue
            if is_test_file(path) and not _has_py_test(tree):
                problems.append(f"{path}: no test function (the file parses but contains no test)")
        elif (
            is_test_file(path)
            and path.endswith((".ts", ".tsx", ".js", ".jsx", ".svelte"))
            and not any(marker in text for marker in _JS_TEST_CALL)
        ):
            problems.append(f"{path}: no test case (the file parses but contains no test)")
    return problems


def _has_py_test(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            return True
        if (
            isinstance(node, ast.ClassDef)
            and node.name.startswith("Test")
            and any(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name.startswith("test")
                for child in node.body
            )
        ):
            return True
    return False


def report(problems: list[str]) -> str:
    """The report line for the self-check fix round."""
    lines = ["ARTIFACTS INCOMPLETE (fix these before QA):"]
    lines.extend(f"  - {problem}" for problem in problems)
    return "\n".join(lines)
