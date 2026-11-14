"""Run one crew under a wall-clock bound (022 follow-up).

`Agent.max_execution_time` stops the *scheduler* after a call, not the call: a
hung provider request kept a 004 replay silent for ~14 minutes while the wall
budget waited for the crew to return. The flow runs a crew in a daemon thread and
joins it with the remaining budget; if it is still alive, the run stops with a
wall-budget record instead of hanging until the runner kills it.

The abandoned thread is a daemon: it cannot write the run's terminal state (the
flow already saved it) and dies with the process.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


def run_bounded(fn: Callable[[], Any], timeout: float, *, name: str = "crew") -> tuple[bool, Any]:
    """Run `fn` for at most `timeout` seconds. Returns (finished, value), or raises.

    A `timeout <= 0` means no bound.
    """
    if timeout <= 0:
        return True, fn()
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - SystemExit from _guard must propagate
            box["error"] = exc

    thread = threading.Thread(target=target, name=f"bounded-{name}", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return False, None
    if "error" in box:
        raise box["error"]
    return True, box.get("value")
