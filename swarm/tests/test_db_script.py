"""`swarm/db.sh` is the one entry point for the local Postgres (005).

Starting Docker in a unit test is not hermetic, so this pins the contract the
Makefile relies on: usage on an unknown verb, and `env` printing nothing (rather
than a broken line) when the container is absent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "db.sh"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args], capture_output=True, text=True, check=False, timeout=60
    )


def test_an_unknown_verb_prints_usage_and_fails():
    result = _run("nonsense")
    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_env_is_silent_when_the_database_is_down(monkeypatch):
    """The Makefile prefixes `DATABASE_URL=…` only when it has one."""
    monkeypatch.setenv("SWARM_DB_CONTAINER", "definitely-not-a-container")
    result = _run("env")
    assert result.stdout.strip() == ""


def test_the_script_is_executable():
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & 0o111, "swarm/db.sh must be executable (make calls it)"
