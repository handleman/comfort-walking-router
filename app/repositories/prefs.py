"""Repository for the ``prefs`` table (per-holder saved route preferences)."""

from __future__ import annotations

import json
from typing import Any

from app.db import get_connection

_GET_PREFS = """
SELECT holder_id, default_preference, created_at, updated_at
FROM prefs
WHERE holder_id = %s
"""

_UPSERT_PREFS = """
INSERT INTO prefs (holder_id, default_preference, created_at, updated_at)
VALUES (%s, %s, NOW(), NOW())
ON CONFLICT (holder_id)
DO UPDATE SET
    default_preference = EXCLUDED.default_preference,
    updated_at = NOW()
RETURNING holder_id, default_preference, created_at, updated_at
"""


def _to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    """Unpack a ``prefs`` row tuple into a dict."""
    holder_id, default_preference, created_at, updated_at = row
    return {
        "holder_id": holder_id,
        "default_preference": default_preference,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def get_prefs(holder_id: str) -> dict[str, Any] | None:
    """Return the saved preferences for ``holder_id`` as a dict, or ``None``."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(_GET_PREFS, (holder_id,))
        row = cur.fetchone()
    return _to_dict(row) if row is not None else None


def update_prefs(holder_id: str, prefs: dict[str, Any]) -> dict[str, Any]:
    """Upsert the preferences for ``holder_id`` and return the saved row."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            _UPSERT_PREFS,
            (holder_id, json.dumps(prefs.get("default_preference"))),
        )
        row = cur.fetchone()
    return _to_dict(row)
