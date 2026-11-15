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
