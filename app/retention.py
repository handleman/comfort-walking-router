"""Retention sweep (spec 005, T7 / AC-7): purge stale saved routes.

Deletes saved routes not accessed within 90 days. Preferences are
intentionally left untouched.
"""

from __future__ import annotations

from app.db import get_connection

_SWEEP_SQL = (
    "DELETE FROM routes "
    "WHERE last_accessed_at < NOW() - INTERVAL '90 days'"
)


def sweep_expired_routes() -> int:
    """Delete routes not accessed in the last 90 days; return row count."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(_SWEEP_SQL)
        return cur.rowcount
