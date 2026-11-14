"""SQLite-backed TTL cache for geocode API responses."""

import json
import os
import sqlite3
import threading
import time
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from .geocoding import Suggestion

TTL_SECONDS = 300

_connections: dict[str, sqlite3.Connection] = {}
# FastAPI runs sync endpoints in a threadpool, so the cached connection must be
# usable from any thread; the reentrant lock serializes access to it.
_lock = threading.RLock()


def _connect() -> sqlite3.Connection:
    """Return a cached sqlite3 connection to the geocode cache database."""
    db_path = os.environ.get("GEOCODE_CACHE_DB", ":memory:")
    with _lock:
        conn = _connections.get(db_path)
        if conn is None:
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS geocode_cache(
                    key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.commit()
            _connections[db_path] = conn
        return conn


def get(key: str) -> list[dict[str, Any]] | None:
    """Return the cached payload list for ``key`` if unexpired, else None."""
    with _lock:
        try:
            row = _connect().execute(
                "SELECT payload, expires_at FROM geocode_cache WHERE key = ?", (key,)
            ).fetchone()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        payload, expires_at = row
        if expires_at is None or expires_at <= time.time():
            try:
                _connect().execute("DELETE FROM geocode_cache WHERE key = ?", (key,))
                _connect().commit()
            except sqlite3.Error:
                pass
            return None
        try:
            loaded = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(loaded, list) or not all(
            isinstance(item, dict) for item in loaded
        ):
            return None
        return loaded


def set(key: str, value: Sequence[dict[str, Any] | Suggestion]) -> None:
    """Upsert ``value`` for ``key`` with an expiry of now + TTL_SECONDS."""
    payload = json.dumps([item if isinstance(item, dict) else asdict(item) for item in value])
    expires_at = time.time() + TTL_SECONDS
    try:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO geocode_cache(key, payload, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                payload = excluded.payload,
                expires_at = excluded.expires_at
            """,
            (key, payload, expires_at),
        )
        conn.commit()
    except sqlite3.Error:
        pass


def clear() -> None:
    """Delete every row from the geocode cache (used by tests)."""
    try:
        conn = _connect()
        conn.execute("DELETE FROM geocode_cache")
        conn.commit()
    except sqlite3.Error:
        pass
