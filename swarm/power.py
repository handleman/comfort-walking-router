"""Keep the host awake while a flow is live (2026-11-26 host-sleep lesson).

T6's verifier call sat silent for 55 minutes because the Mac slept mid-request;
on wake the client reported `Request timed out`, which read exactly like a hung
model. `caffeinate -ims -w <pid>` holds an assertion for the life of this
process, so a queue run cannot be suspended half-way.

No-op off macOS, when `caffeinate` is missing, and with `SWARM_KEEP_AWAKE=0`.
"""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping

_proc: subprocess.Popen[bytes] | None = None


def enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get("SWARM_KEEP_AWAKE", "1")).strip() != "0"


def keep_awake() -> subprocess.Popen[bytes] | None:
    """Spawn the idle-sleep assertion once; returns the child (or None)."""
    global _proc
    if _proc is not None:
        return _proc
    if sys.platform != "darwin" or not enabled():
        return None
    exe = shutil.which("caffeinate")
    if not exe:
        return None
    try:
        _proc = subprocess.Popen(
            [exe, "-i", "-m", "-s", "-w", str(os.getpid())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        _proc = None
        return None
    atexit.register(release)
    print(f"keep-awake: caffeinate -ims (watching pid {os.getpid()})", flush=True)
    return _proc


def release() -> None:
    """Stop the assertion child (idempotent; atexit-safe)."""
    global _proc
    proc, _proc = _proc, None
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
    except OSError:
        pass
