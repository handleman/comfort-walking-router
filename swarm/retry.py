"""Retry/backoff classification (012 T13).

Kept dependency-free so the flow can decide *when* to retry, when to switch to
fallback models, and when to stop (daily quota) without importing provider SDKs.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

RETRY_HINTS = (
    "429",
    "rate limit",
    "ratelimit",
    "too many requests",
    "timeout",
    "timed out",
    "connection",
    "overloaded",
    "temporarily unavailable",
    "502",
    "503",
    "504",
)

QUOTA_HINTS = ("free-models-per-day", "daily quota", "quota exceeded")


def is_retryable(exc: BaseException) -> bool:
    s = f"{type(exc).__name__}: {exc}".lower()
    return any(h in s for h in RETRY_HINTS)


CONFIG_HINTS = (
    "<!doctype",
    "<html",
    "404",
    "401",
    "403",
    "invalid api key",
    "unauthorized",
    "no auth",
    "not found",
    "invalid response from llm call - none or empty",
    "model not found",
    "does not exist",
)


def classify_provider_error(exc: BaseException) -> str:
    """`config` (terminal), `retryable` (backoff), or `unknown` (give up)."""
    text = f"{type(exc).__name__}: {exc}".lower()
    if any(h in text for h in ("<!doctype", "<html")):
        return "config"
    if is_quota_error(exc):
        return "quota"
    if is_retryable(exc):
        return "retryable"
    if any(h in text for h in CONFIG_HINTS):
        return "config"
    return "unknown"


def is_quota_error(exc: BaseException) -> bool:
    """Daily free-tier quota: retrying the same model is pointless."""
    s = f"{type(exc).__name__}: {exc}".lower()
    return any(h in s for h in QUOTA_HINTS)


def backoff_delay(attempt: int, *, base: float = 1.0, cap: float = 8.0, jitter: float = 0.25) -> float:
    """Exponential backoff for 1-based attempt with a little jitter."""
    delay = min(cap, base * (2 ** max(0, attempt - 1)))
    return delay + random.uniform(0, jitter)


def call_with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    should_retry: Callable[[BaseException], bool] = is_retryable,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> T:
    last: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except BaseException as e:
            last = e
            if attempt >= attempts or not should_retry(e):
                raise
            delay = backoff_delay(attempt, base=base)
            if on_retry is not None:
                on_retry(attempt, e, delay)
            sleep(delay)
    assert last is not None
    raise last
