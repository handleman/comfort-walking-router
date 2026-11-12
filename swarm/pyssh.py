"""An `ssh` replacement for git's transport, implemented with paramiko.

git invokes its ssh command as::

    <command> [-p <port>] <host> <remote command...>

This module honours that contract: it connects with the ssh-agent's key
(the key never touches disk), resolves the host with `dig` when the shell
has no resolver, and pipes the session's stdin/stdout/stderr to the local
process. git then speaks its own wire protocol over the pipe, so this module
does not have to know anything about `git-receive-pack`.

Why it exists: in some agent shells `/usr/bin/ssh` cannot start at all
("No user exists for uid 501"), so git's own transport never reaches the
handshake. `GIT_SSH_COMMAND="<python> swarm/pyssh.py"` keeps git's semantics
and makes the transport work.

Usage:
    GIT_SSH_COMMAND="python3 swarm/pyssh.py" git push origin main
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
from pathlib import Path


def _resolve_ip(host: str) -> str:
    """Resolve `host` to an IP without the system resolver.

    `dig` reads /etc/resolv.conf directly, so it works where getaddrinfo does
    not. The host key is still verified against the hostname, never the IP.
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


def _connect(host: str, port: int):
    """Open an authenticated session to `host` and return the client."""
    import paramiko

    client = paramiko.SSHClient()
    client.load_system_host_keys(str(Path.home() / ".ssh" / "known_hosts"))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())

    # The socket goes to the resolved IP (this shell may have no resolver),
    # but paramiko looks the host key up by `hostname`, so the key is always
    # verified against the name we asked for.
    try:
        socket.getaddrinfo(host, port)[0][4][0]
        sock = None
    except OSError:
        sock = socket.create_connection((_resolve_ip(host), port), timeout=30)

    kwargs: dict[str, object] = {
        "hostname": host,
        "port": port,
        "username": os.environ.get("SWARM_SSH_USER", "git"),
        "allow_agent": True,
        "look_for_keys": False,
        "timeout": 30,
    }
    if sock is not None:
        kwargs["sock"] = sock
    client.connect(**kwargs)  # type: ignore[arg-type]
    return client


def _pump(channel, source) -> None:
    """Copy `source` into the channel until EOF."""
    try:
        while True:
            data = source.read(65536)
            if not data:
                break
            channel.sendall(data)
    except (OSError, ValueError):
        pass
    finally:
        try:
            channel.shutdown_write()
        except (OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    port = 22
    while args and args[0] == "-p":
        args.pop(0)
        port = int(args.pop(0))
    if not args:
        print("usage: pyssh.py [-p port] <host> <command...>", file=sys.stderr)
        return 2
    host = args.pop(0)
    command = " ".join(args)

    # git passes the remote as `user@host`; the user is the ssh user.
    user = os.environ.get("SWARM_SSH_USER", "")
    if "@" in host:
        user, host = host.split("@", 1)
    if user:
        os.environ["SWARM_SSH_USER"] = user

    client = _connect(host, port)
    try:
        channel = client.get_transport().open_session()
        channel.exec_command(command)

        stdin_thread = threading.Thread(
            target=_pump, args=(channel, sys.stdin.buffer), daemon=True
        )
        stdin_thread.start()

        while True:
            data = channel.recv(65536)
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        stdin_thread.join(timeout=5)
        return channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
