"""Unattended queue supervisor (015 AC-9).

Restarts the pilot after retryable outcomes, parks tasks that exhausted their
attempts as `retry_later`, and keeps going with the next runnable task. One
command: `make swarm-supervise`.

Stop conditions: `config_error`, empty queue (every task green/done), the run
budget, the attempt cap for every remaining task, or a `swarm/STOP` file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from swarm.spec_loader import task_key

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS = REPO_ROOT / "swarm" / "runs"
RETRY_LATER = RUNS / "retry_later.json"
STOP_FILE = REPO_ROOT / "swarm" / "STOP"

RETRYABLE = {
    "interrupted",
    "crew_error",
    "quota_exhausted",
    "budget_exhausted",
    "preflight_failed",
    "commit_failed",
    "push_failed",
    "merge_failed",
}
TERMINAL = {"config_error"}
DONE = {"green"}


@dataclass
class Outcome:
    status: str
    spec: str = ""
    task: str = ""
    run_dir: str = ""

    @property
    def action(self) -> str:
        if self.status in DONE:
            return "continue"
        if self.status in TERMINAL:
            return "stop"
        if self.status in RETRYABLE:
            return "retry"
        return "stop"


def latest_run(runs: Path = RUNS) -> Path | None:
    if not runs.is_dir():
        return None
    dirs = sorted(p for p in runs.iterdir() if p.is_dir() and p.name[:1].isdigit())
    for path in reversed(dirs):
        if (path / "run.json").is_file():
            return path
    return None


def read_outcome(run_dir: Path) -> Outcome:
    try:
        payload: dict[str, Any] = json.loads((run_dir / "run.json").read_text())
    except (OSError, json.JSONDecodeError):
        return Outcome("crew_error", run_dir=str(run_dir))
    return Outcome(
        status=str(payload.get("status") or "crew_error"),
        spec=str(payload.get("spec") or ""),
        task=str(payload.get("task") or ""),
        run_dir=str(run_dir),
    )


def load_attempts(path: Path = RETRY_LATER) -> dict[str, int]:
    """Attempt counts; also reads the legacy flat `{key: count}` schema."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    raw = data.get("attempts")
    if not isinstance(raw, dict):
        raw = data  # legacy: the whole file was the attempts map
    return {str(k): int(v) for k, v in raw.items() if isinstance(v, int | float)}


def save_attempts(attempts: dict[str, int], path: Path = RETRY_LATER) -> None:
    """Write counts *and* keep the parked list; they share one file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"attempts": dict(attempts), "retry_later": _existing_later(path)}
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    except OSError:
        pass


def supervise(
    *,
    max_attempts: int = 3,
    base_delay: float = 30.0,
    cap_delay: float = 600.0,
    max_rounds: int = 20,
    runner: Callable[[], int] | None = None,
    runs: Path = RUNS,
    stop_file: Path = STOP_FILE,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> int:
    """Run/resume the queue until it is done. Returns the last exit code."""
    attempts = load_attempts()
    run_once = runner or _default_runner
    for round_no in range(1, max_rounds + 1):
        if stop_file.exists():
            log(f"supervisor: {stop_file} present — stopping")
            return 0
        code = run_once()
        run_dir = latest_run(runs)
        if run_dir is None:
            log("supervisor: no run produced — stopping")
            return code
        outcome = read_outcome(run_dir)
        # run.json records the invocation prefix (`007`); park the canonical
        # directory name so the flow's own parked-task check matches it.
        key = task_key(runs.parent.parent, outcome.spec, outcome.task)
        log(f"supervisor: {key} → {outcome.status} ({outcome.action})")
        if outcome.action == "continue":
            log("supervisor: queue finished")
            return code
        if outcome.action == "stop":
            log(f"supervisor: terminal outcome {outcome.status} — stopping")
            return code
        attempts[key] = attempts.get(key, 0) + 1
        save_attempts(attempts)
        if attempts[key] >= max_attempts:
            log(f"supervisor: {key} exhausted {max_attempts} attempts → retry_later")
            mark_retry_later(key)
            # The queue skips parked tasks on the next resume; keep the pause
            # short so the remaining work still moves tonight.
            attempts[key] = 0
            delay = base_delay
        else:
            delay = min(cap_delay, base_delay * (2 ** (attempts[key] - 1)))
        log(f"supervisor: retrying in {delay:.0f}s (attempt {attempts[key]}/{max_attempts})")
        sleep(delay)
    log("supervisor: round cap reached — stopping")
    return 1


def mark_retry_later(key: str, path: Path = RETRY_LATER) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if "/" in key:
            spec, task = key.split("/", 1)
            key = task_key(path.parent.parent.parent, spec, task)
        data = load_attempts(path)
        data.setdefault(key, 0)
        payload = {"attempts": data, "retry_later": sorted({*_existing_later(path), key})}
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    except OSError:
        pass


def _existing_later(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return [str(v) for v in data.get("retry_later", [])] if isinstance(data, dict) else []


def _default_runner() -> int:
    cmd = [str(REPO_ROOT / "swarm" / "run.sh"), "--resume"]
    return subprocess.run(cmd, cwd=REPO_ROOT, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    max_rounds = int(os.getenv("SWARM_SUPERVISE_ROUNDS", "20"))
    max_attempts = int(os.getenv("SWARM_SUPERVISE_ATTEMPTS", "3"))
    return supervise(max_rounds=max_rounds, max_attempts=max_attempts)


if __name__ == "__main__":
    raise SystemExit(main())
