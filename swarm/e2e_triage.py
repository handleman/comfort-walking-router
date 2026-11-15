"""Triage a red end-to-end run (027 T1, AC-1).

A red Playwright run is not one problem. The 2026-11-15 runs showed four in one
afternoon: a stale test datum, two real product defects, a config argv that made
every test fail for the wrong reason. Fixing the wrong class wastes the whole
budget — editing the test to hide a product bug is worse, it deletes the oracle.

Everything here is deterministic and offline: parse the *recorded* run out of
`shell_log.jsonl`, name each failing test, and sort each into one class with a
decision table. No model call, so a wrong verdict is a failing unit test rather
than a prompt to argue with (`docs/research/self-healing-e2e-2026.md` — Donobu
and RoostGPT both classify before touching anything).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Reason codes the flow turns into stops.
CLASSES = ("env", "flaky", "coverage", "impl", "drift", "unclassified")

# `  ✘ 3 frontend/e2e/walk-mode.spec.ts:31:1 › walk mode shows the reroute …`
_FAIL_LINE = re.compile(
    r"^\s*[✘✗×]\s*\d*\s*(?:\[[^\]]+\]\s*›\s*)?"
    r"(?P<file>[\w./-]+\.(?:spec|test)\.ts):(?P<line>\d+):\d+\s*›\s*(?P<title>.+?)\s*$",
    re.MULTILINE,
)
# `  1) frontend/e2e/walk-mode.spec.ts:5:1` (the summary block)
_FAIL_HEADER = re.compile(
    r"^\s*\d+\)\s*(?P<file>[\w./-]+\.(?:spec|test)\.ts):(?P<line>\d+):\d+",
    re.MULTILINE,
)

# Error classes, most specific first. The order is the decision table.
_ENV_MARKERS = (
    "cannot navigate to invalid url",
    "econnrefused",
    "database_url is not configured",
    "browser has been closed",
    "net::err_connection_refused",
    "executable doesn't exist",
    "playwright install",
)
_DRIFT_MARKERS = (
    "element(s) not found",
    "waiting for locator",
    "locator.click: timeout",
    "strict mode violation",
)
_IMPL_MARKERS = (
    "expected substring",
    "expected:",
    "tohavebevisible",
    "tohavetext",
    "tohavecount",
)


@dataclass(frozen=True)
class FailedTest:
    """One failing test, as the recorded run reported it."""

    file: str
    line: int
    title: str
    cls: str = "unclassified"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "title": self.title,
            "class": self.cls,
            "reasons": list(self.reasons),
        }


def _strip_prefix(path: str) -> str:
    """The reporter prints `frontend/e2e/x.spec.ts` or `e2e/x.spec.ts`."""
    path = path.replace("\\", "/").lstrip("./")
    return path.removeprefix("frontend/")


def failing_tests(executions: list[dict[str, Any]]) -> list[FailedTest]:
    """Failing tests from the newest recorded Playwright execution."""
    run = latest_suite_run(executions)
    if run is None:
        return []
    tail = str(run.get("tail") or "")
    out: list[FailedTest] = []
    seen: set[tuple[str, str]] = set()
    for match in _FAIL_LINE.finditer(tail):
        path, title = _strip_prefix(match.group("file")), match.group("title").strip()
        if (path, title) in seen:
            continue
        seen.add((path, title))
        out.append(FailedTest(file=path, line=int(match.group("line")), title=title))
    if out:
        return out
    # A crashed run (config error, missing backend) has headers but no titles.
    for match in _FAIL_HEADER.finditer(tail):
        path = _strip_prefix(match.group("file"))
        if any(path == seen_path for seen_path, _ in seen):
            continue
        seen.add((path, ""))
        out.append(FailedTest(file=path, line=int(match.group("line")), title=""))
    return out


def latest_suite_run(executions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The last recorded e2e execution (any agent, any hash)."""
    from swarm import evidence

    runs = evidence.e2e_executions(executions or [])
    return runs[-1] if runs else None


def classify(
    failed: list[FailedTest],
    *,
    tail: str = "",
    spec_exists: dict[str, bool] | None = None,
    fixture_ok: bool = True,
    retried_pass: bool = False,
) -> list[FailedTest]:
    """Sort every failure into one class (AC-1); unknown stays unclassified."""
    if not failed:
        return []
    spec_exists = spec_exists or {}
    text = (tail or "").lower()
    if retried_pass:
        return [FailedTest(f.file, f.line, f.title, "flaky", ("passed on retry",)) for f in failed]
    out: list[FailedTest] = []
    for fail in failed:
        reasons: list[str] = []
        cls = "unclassified"
        if not fixture_ok:
            cls, reasons = "env", ("fixture backend unavailable",)
        elif any(marker in text for marker in _ENV_MARKERS):
            # A broken environment invalidates every other signal: repairing a
            # spec because the backend was down is how a suite gets weakened.
            cls, reasons = "env", ("environment/configuration error in the suite output",)
        elif not spec_exists.get(fail.file, True):
            cls, reasons = "coverage", ("the brief names this spec and it does not exist",)
        elif not fail.title:
            cls, reasons = "env", ("the run failed before a test title was reported",)
        elif any(marker in text for marker in _DRIFT_MARKERS):
            cls, reasons = "drift", ("a locator the spec expects is not in the page",)
        elif any(marker in text for marker in _IMPL_MARKERS):
            cls, reasons = "impl", ("the page is there but its behaviour differs",)
        out.append(FailedTest(fail.file, fail.line, fail.title, cls, tuple(reasons)))
    return out


def classify_run(
    executions: list[dict[str, Any]],
    *,
    spec_exists: dict[str, bool] | None = None,
    fixture_ok: bool = True,
) -> tuple[list[FailedTest], dict[str, Any]]:
    """Parse + classify the newest recorded run; returns (failures, run record)."""
    run = latest_suite_run(executions) or {}
    failed = failing_tests(executions)
    tail = str(run.get("tail") or "")
    classes = classify(
        failed, tail=tail, spec_exists=spec_exists, fixture_ok=fixture_ok
    )
    return classes, run


def digest(failed: list[FailedTest], tail: str = "", *, max_chars: int = 3000) -> str:
    """Bounded prompt block: one line per failure plus the error tail."""
    header = "FAILING E2E TESTS\n"
    rows = "\n".join(
        f"- {f.file}:{f.line} › {f.title or '<no title>'} [{f.cls}]"
        for f in failed
    ) or "- (none parsed)"
    body = tail.strip()[-max_chars:]
    return f"{header}{rows}\n\nERROR OUTPUT (tail)\n{body}\n"


def primary_class(failed: list[FailedTest]) -> str:
    """The class the phase acts on: any env wins, then coverage, drift, impl."""
    classes = {f.cls for f in failed}
    for name in ("env", "flaky", "coverage", "drift", "impl"):
        if name in classes:
            return name
    return "unclassified" if classes else ""
