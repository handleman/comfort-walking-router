"""`make e2e`: build the frontend and run the Playwright suite (026 AC-8).

The suite is the only evidence that a user scenario works. 010-T4 was green
having touched only `helpers.ts`; no gate could tell, because the harness never
ran Playwright. This module is the one supported entry point: it builds the app
and runs `playwright test` from `frontend/`, where the config boots the fixture
backend (`ROUTE_FIXTURES=1`) and `vite preview` itself.

`make e2e` is also what the harness records as evidence for a task whose brief
names `frontend/e2e/*` (see `swarm/evidence.py::e2e_executions`). The execution
lands in the run's `shell_log.jsonl` only when the *agent* ran it; an operator
running `make e2e` is doing the same check by hand.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND = REPO_ROOT / "frontend"
PLAYWRIGHT_BIN = FRONTEND / "node_modules" / ".bin" / "playwright"


def command() -> list[str]:
    """The exact argv the harness looks for (`playwright … test`)."""
    return ["npx", "playwright", "test"]


SPEC_RE = re.compile(r"frontend/(e2e/[\w./-]+\.ts)")


def specs_in(text: str) -> list[str]:
    """`frontend/e2e/x.spec.ts` paths named by a brief, as QA's cwd sees them."""
    seen: list[str] = []
    for match in SPEC_RE.findall(text or ""):
        if match not in seen:
            seen.append(match)
    return seen


def agent_commands(brief: str = "") -> list[list[str]]:
    """What QA must run, in order, to produce e2e evidence (026 AC-8).

    `vite preview` serves `dist/`, so a stale build would test the previous
    commit — the build is part of the evidence. Only the brief's own spec files
    are named when it names any: the task's acceptance scenario is the one that
    has to pass, and QA still runs every gate.
    """
    specs = specs_in(brief)
    return [
        ["npm", "--prefix", "frontend", "run", "build"],
        ["npm", "--prefix", "frontend", "exec", "playwright", "test", *specs],
    ]


def browsers(repo_root: Path | None = None) -> list[str]:
    """Are the Chromium binaries installed? (offline: `install --dry-run`)

    Browsers are a separate download from `npm install`; without them every e2e
    run fails inside Playwright after the build. `--dry-run` prints the expected
    install locations and makes no network call.
    """
    root = Path(repo_root or REPO_ROOT)
    binary = root / "frontend" / "node_modules" / ".bin" / "playwright"
    if not binary.exists():
        return []  # `available` already reports the missing binary
    try:
        proc = subprocess.run(
            [str(binary), "install", "--dry-run", "chromium"],
            cwd=root / "frontend",
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return [f"`playwright install --dry-run` failed: {e}"]
    locations = [
        line.split("Install location:", 1)[1].strip()
        for line in (proc.stdout + proc.stderr).splitlines()
        if "Install location:" in line
    ]
    if not locations or any(Path(path).exists() for path in locations):
        return []
    return [
        (
            "Playwright browsers are not installed "
            "(run `npm --prefix frontend exec playwright install chromium`)"
        )
    ]


def available(repo_root: Path | None = None) -> list[str]:
    """Why the suite cannot run here; empty when it can.

    `repo_root` lets preflight ask about the checkout it is checking (tests use
    a tmp tree); the default is this module's repo.
    """
    root = Path(repo_root or REPO_ROOT)
    frontend = root / "frontend"
    problems: list[str] = []
    if shutil.which("npx") is None:
        problems.append("`npx` is not on PATH")
    if not (frontend / "node_modules" / ".bin" / "playwright").exists():
        problems.append(
            "frontend/node_modules/.bin/playwright is missing "
            "(run `npm --prefix frontend install`)"
        )
    if not (frontend / "playwright.config.ts").is_file():
        problems.append("frontend/playwright.config.ts is missing")
    problems += browsers(root)
    return problems


def _run(argv: list[str], *, cwd: Path) -> int:
    print(f"$ {' '.join(argv)}  (cwd={cwd})", flush=True)
    proc = subprocess.run(argv, cwd=cwd, check=False)
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    extra = list(argv or sys.argv[1:])
    problems = available()
    if problems:
        for problem in problems:
            print(f"e2e: {problem}", file=sys.stderr)
        return 2
    built = _run(["npm", "run", "build"], cwd=FRONTEND)
    if built != 0:
        return built
    return _run(["npx", "playwright", "test", *extra], cwd=FRONTEND)


if __name__ == "__main__":
    raise SystemExit(main())
