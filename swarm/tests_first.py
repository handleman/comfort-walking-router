"""Tests-first phase (021 T4, AC-4).

The 020 history's long repairs are usually assertion churn: the coder writes the
test and the implementation in the same trajectory, so a wrong assumption is
encoded twice (014-T7's client read `results` while the pinned plan said
`suggestions`). A tests-first phase writes the failing test **from the
acceptance criteria first**, freezes it, and then the implementation steps must
make it pass.

Two guardrails, both from the 2026 evidence:

- the test author is a separate role with no shell and write access to test paths
  only (ExecCritic: an author that can also patch the implementation tends to
  agree with its own mistake);
- the phase is an A/B (`SWARM_TESTS_FIRST=1`, default 0). A weak test author can
  perform *worse* than no test, so it ships only on a measured win.

Frozen tests are blocked at the tool layer (`tools_guarded._write_target`), so a
step crew cannot quietly rewrite the check it is supposed to satisfy.
"""

from __future__ import annotations

import hashlib
import os
import posixpath
from collections.abc import Iterable, Mapping

ENABLE_ENV = "SWARM_TESTS_FIRST"

_TEST_MARKERS = (
    "/tests/",
    "tests/",
    "/test_",
    "test_",
    "/e2e/",
    "e2e/",
    ".test.",
    ".spec.",
    "_test.",
)
WALK_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".svelte")


def enabled(env: Mapping[str, str] | None = None) -> bool:
    source: Mapping[str, str] = os.environ if env is None else env
    return str(source.get(ENABLE_ENV, "0")).strip().lower() in {"1", "true", "yes"}


def is_test_path(path: str) -> bool:
    """True for a test/e2e file (the only paths the Test Author may write)."""
    norm = "/" + str(path).replace("\\", "/").lstrip("./")
    return any(marker in norm for marker in _TEST_MARKERS)


def command_for(paths: Iterable[str], gates: Iterable[str]) -> str:
    """The test command for these paths, chosen from the project's own gates.

    A frontend test runs the project's frontend test gate; anything else runs the
    first gate that looks like a test command. Falls back to `pytest -q` so the
    phase still works on a checkout without configured gates.
    """
    gates = list(gates)
    frontend = any(str(p).replace("\\", "/").startswith("frontend/") for p in paths)
    for gate in gates:
        low = gate.lower()
        if "test" not in low and "vitest" not in low:
            continue
        if frontend and "frontend" in low:
            return gate
        if not frontend and "frontend" not in low:
            return gate
    if frontend:
        return "npm --prefix frontend test -- --run"
    return "pytest -q"


# ---- freeze registry (process-wide; the harness runs one task at a time) ----

_frozen: dict[str, str] = {}


def freeze(paths: Iterable[str], contents: Mapping[str, str] | None = None) -> dict[str, str]:
    """Freeze test files by path (and content hash); return the registry."""
    _frozen.clear()
    for path in paths:
        text = (contents or {}).get(path, "")
        _frozen[str(path)] = hashlib.sha256(text.encode()).hexdigest() if text else ""
    return dict(_frozen)


def clear() -> None:
    _frozen.clear()


def frozen() -> dict[str, str]:
    return dict(_frozen)


def is_frozen(path: str) -> bool:
    return str(path).replace("\\", "/").lstrip("./") in {
        key.replace("\\", "/").lstrip("./") for key in _frozen
    }


def frozen_note() -> str:
    """The line appended to implementation prompts while tests are frozen."""
    if not _frozen:
        return ""
    return (
        "A test author wrote and froze these tests before implementation: "
        + ", ".join(sorted(posixpath.normpath(p) for p in _frozen))
        + ". They encode the acceptance criteria: make them pass without editing them. "
        "If a frozen test is genuinely wrong, stop and report it; do not rewrite it."
    )
