"""053 AC-5: `make swarm-health` — prove the test stand before a queue run.

A stale `playwright.config.ts` (`webServer.cwd: 'frontend'`) kept the e2e suite
from launching for several runs, and nothing noticed until an explicit
`make e2e`. This runs the app tests and the e2e suite in one command and exits
non-zero with the tail when either is broken.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(argv: list[str], *, label: str) -> str | None:
    try:
        proc = subprocess.run(
            argv,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{label}: could not run: {exc}"
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr)[-600:].strip()
        return f"{label}: exit {proc.returncode}\n{tail}"
    return None


def check() -> list[str]:
    """Every broken part of the stand; empty means healthy."""
    problems: list[str] = []
    app_python = REPO_ROOT / ".venv" / "bin" / "python"
    swarm_python = REPO_ROOT / "swarm" / ".venv" / "bin" / "python"
    if app_python.exists():
        problem = _run([str(app_python), "-m", "pytest", "-q"], label="app tests")
        if problem:
            problems.append(problem)
    else:
        problems.append(f"app venv missing: {app_python} (run `make dev-setup`)")
    if swarm_python.exists():
        problem = _run([str(swarm_python), "-m", "swarm.e2e"], label="e2e suite")
        if problem:
            problems.append(problem)
    else:
        problems.append(f"swarm venv missing: {swarm_python} (run `make swarm-test`)")
    return problems


def main() -> int:
    problems = check()
    if problems:
        print("swarm-health: FAIL")
        for problem in problems:
            print(" -", problem)
        return 1
    print("swarm-health: OK (app tests + e2e suite green)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
