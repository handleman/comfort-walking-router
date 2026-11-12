"""Push to GitHub over SSH using paramiko (agent auth), bypassing /usr/bin/ssh.

Why this exists: the agent shell that runs the assistant has no passwd entry
for its uid, so `/usr/bin/ssh` aborts with "No user exists for uid 501" and
`getaddrinfo` cannot resolve github.com (no DNS in that context). Git's own
`ssh` transport therefore cannot start.

This module speaks the git-over-SSH wire protocol directly:
`git-receive-pack <repo>` on the remote, with the packfile produced locally by
`git pack-objects`. The ssh-agent already holds the user's GitHub key, so the
key never touches disk here.

Usage:
    python -m swarm.gitpush <remote-url> <branch>
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_ip(host: str) -> str:
    """Resolve `host` without the system resolver (this shell has none).

    `dig` reads /etc/resolv.conf directly, so it works where getaddrinfo does
    not. The host key is still checked against the hostname, never the IP.
    """
    try:
        out = subprocess.run(
            ["dig", "+short", host],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        ).stdout.decode()
    except OSError:
        out = ""
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith(";"):
            return line
    raise RuntimeError(f"cannot resolve {host}")


def _git(*args: str, cwd: Path | None = None, stdin: bytes | None = None) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd or REPO_ROOT),
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace')[:500]}"
        )
    return proc.stdout


def _parse_ssh_url(url: str) -> tuple[str, str, int]:
    """`git@github.com:owner/repo.git` → (host, owner/repo.git, port)."""
    m = re.match(r"^(?:ssh://)?(?:([^@/]+)@)?([^:/]+)(?::(\d+))?[:/](.+)$", url)
    if not m:
        raise ValueError(f"cannot parse ssh url: {url!r}")
    user, host, port, path = m.groups()
    return host, path, int(port or 22)


def _agent_key(paramiko_mod):
    """The agent's key for github.com, or None."""
    sock = os.environ.get("SSH_AUTH_SOCK")
    if not sock:
        return None
    keys = paramiko_mod.Agent().get_keys()
    for key in keys:
        comment = getattr(key, "comment", "") or ""
        if "github" in comment.lower():
            return key
    return keys[0] if keys else None


def push(remote_url: str, branch: str = "main", *, cwd: Path | None = None) -> int:
    """Push `branch` to `remote_url` over SSH. Returns a process exit code."""
    import paramiko

    repo = cwd or REPO_ROOT
    host, path, port = _parse_ssh_url(remote_url)

    # What the remote currently has, and what we are sending.
    remote_ref = f"refs/heads/{branch}"
    local_sha = _git("rev-parse", "refs/heads/" + branch, cwd=repo).decode().strip()
    want = f"{local_sha} {remote_ref}"

    client = paramiko.SSHClient()
    client.load_system_host_keys(str(Path.home() / ".ssh" / "known_hosts"))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    # This shell has no resolver, so connect to the IP and keep verifying the
    # key against the *hostname* we asked for (never against the IP).
    connect_host = host
    try:
        socket.getaddrinfo(host, port)[0][4][0]
    except OSError:
        connect_host = _resolve_ip(host)
    client.connect(
        hostname=connect_host,
        port=port,
        username="git",
        key_filename=None,
        allow_agent=True,
        look_for_keys=False,
        timeout=30,
        server_hostkey_name=host,
    )
    try:
        channel = client.get_transport().open_session()
        channel.exec_command(f"git-receive-pack '{path}'")

        # git's pkt-line protocol: the client sends its wants first.
        channel.sendall(b"0000")  # flush
        channel.sendall(f"{want}\0".encode() + b"0000")

        # Then the packfile, and the stats the remote sends back.
        pack = _git(
            "pack-objects",
            "--stdout",
            "--revs",
            "--thin",
            "--delta-base-offset",
            cwd=repo,
            stdin=f"{local_sha}\n".encode(),
        )
        channel.sendall(pack)
        channel.sendall(b"0000")

        out = b""
        while True:
            chunk = channel.recv(65536)
            if not chunk:
                break
            out += chunk
        channel.close()
    finally:
        client.close()

    text = out.decode("utf-8", "replace")
    print(text.strip() or "(no output)")
    if "reject" in text or "error" in text.lower():
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="git push over ssh via paramiko")
    ap.add_argument("remote", nargs="?", default="origin")
    ap.add_argument("branch", nargs="?", default="main")
    args = ap.parse_args(argv)

    url = _git("remote", "get-url", args.remote).decode().strip()
    if not url.startswith("git@") and not url.startswith("ssh://"):
        print(f"remote {args.remote} is not an ssh url: {url}")
        return 1
    try:
        return push(url, args.branch)
    except Exception as e:
        print(f"push failed: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
