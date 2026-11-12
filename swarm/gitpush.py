"""Push a branch to a git remote from an agent shell.

Why this exists: a broken `core.sshCommand` in the git config (a helper that
was never written, e.g. `/path/to/py_ssh.py`) makes *every* `git push` die
before the handshake, including the harness's own push in `swarm/flow.py`.
This module pushes with an explicit, working ssh command instead of
inheriting whatever the config says.

Two strategies, in order:

1. `git push` with `core.sshCommand` set to a usable ssh binary
   (`SWARM_SSH_COMMAND`, default `/usr/bin/ssh`).
2. `git push` through `swarm/pyssh.py`, a small paramiko-based ssh client
   for shells where `/usr/bin/ssh` cannot start at all.

Usage:
    python -m swarm.gitpush [remote] [branch]
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYSSH = Path(__file__).resolve().parent / "pyssh.py"


def _git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd or REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    out = proc.stdout.decode("utf-8", "replace")
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed ({proc.returncode}): {out[:500]}")
    return out


def _ssh_commands() -> list[str]:
    """The ssh commands to try, most usable first."""
    commands: list[str] = []
    override = os.environ.get("SWARM_SSH_COMMAND", "").strip()
    if override:
        commands.append(override)
    if Path("/usr/bin/ssh").exists():
        commands.append("/usr/bin/ssh")
    commands.append(f"{sys.executable} {PYSSH}")
    return commands


def push(
    remote: str = "origin",
    branch: str = "main",
    *,
    cwd: Path | None = None,
    args: list[str] | None = None,
) -> int:
    """Push `branch` to `remote`. Returns a process exit code.

    `args` overrides the default `<remote> <branch>` (the harness pushes
    `origin <branch>` and `origin <base>`).
    """
    repo = cwd or REPO_ROOT
    target = list(args) if args is not None else [remote, branch]
    # The remote to look up: the first non-flag argument of the push target.
    push_remote = next((a for a in target if not a.startswith("-")), remote)
    url = _git("remote", "get-url", push_remote, cwd=repo).strip()
    if not url.startswith("git@") and not url.startswith("ssh://"):
        print(f"{push_remote} is not an ssh remote ({url}); pushing directly")
        proc = subprocess.run(
            ["git", "push", *target], cwd=str(repo), check=False
        )
        return proc.returncode

    last = ""
    for ssh in _ssh_commands():
        cmd = ["git", "-c", f"core.sshCommand={ssh}", "push", *target]
        proc = subprocess.run(cmd, cwd=str(repo), check=False)
        if proc.returncode == 0:
            print(f"pushed {' '.join(target)} (ssh: {ssh})")
            return 0
        last = f"ssh={ssh} rc={proc.returncode}"
        print(f"push failed with {last}; trying the next transport")
    print(f"push failed: {last}")
    return 1


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="git push with a working ssh transport")
    parser.add_argument("remote", nargs="?", default="origin")
    parser.add_argument("branch", nargs="?", default="main")
    args = parser.parse_args(argv)
    try:
        return push(args.remote, args.branch)
    except Exception as e:  # noqa: BLE001 - the CLI reports, it does not trace
        print(f"push failed: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
