"""Saved-route repository (psycopg, holder_id-scoped)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.db import get_connection

_UPSERT = """
INSERT INTO routes (id, holder_id, request, response)
VALUES (%s, %s, %s, %s)
ON CONFLICT (holder_id, id) DO UPDATE
SET request = EXCLUDED.request,
    response = EXCLUDED.response,
    last_accessed_at = NOW()
RETURNING id, holder_id, request, response, created_at, last_accessed_at
"""

_SELECT = """
SELECT id, holder_id, request, response, created_at, last_accessed_at
FROM routes
WHERE holder_id = %s
ORDER BY created_at DESC
"""


def save_route(
    holder_id: str, route_id: str, request: dict[str, Any], response: dict[str, Any]
) -> dict[str, Any]:
    """Insert or update a saved route, scoped to holder_id."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            _UPSERT,
            (str(uuid.UUID(route_id)), holder_id, json.dumps(request), json.dumps(response)),
        )
        row = cur.fetchone()
    return _to_dict(row)


def list_routes(holder_id: str) -> list[dict[str, Any]]:
    """List saved routes for holder_id only (never other holders')."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(_SELECT, (holder_id,))
        rows = cur.fetchall()
    return [_to_dict(row) for row in rows]


_RECALL = """
UPDATE routes
SET last_accessed_at = NOW()
WHERE holder_id = %s AND id = %s
RETURNING id, holder_id, request, response, created_at, last_accessed_at
"""


def recall_route(holder_id: str, route_id: str) -> dict[str, Any] | None:
    """Fetch one saved route for holder_id, refreshing last_accessed_at.

    Returns None when the route is missing or belongs to another holder (404).
    """
    try:
        route_uuid = str(uuid.UUID(route_id))
    except ValueError:
        return None
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(_RECALL, (holder_id, route_uuid))
        row = cur.fetchone()
    return _to_dict(row) if row else None


_DELETE = """
DELETE FROM routes
WHERE holder_id = %s AND id = %s
"""


def delete_route(holder_id: str, route_id: str) -> bool:
    """Delete one saved route for holder_id.

    Returns False when the route is missing or belongs to another holder (404).
    """
    try:
        route_uuid = str(uuid.UUID(route_id))
    except ValueError:
        return False
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(_DELETE, (holder_id, route_uuid))
        deleted = cur.rowcount > 0
    return deleted


def _to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        route_id,
        holder_id,
        request,
        response,
        created_at,
        last_accessed_at,
    ) = row
    return {
        "id": str(route_id),
        "holder_id": holder_id,
        "request": request if isinstance(request, dict) else json.loads(request),
        "response": response if isinstance(response, dict) else json.loads(response),
        "created_at": created_at,
        "last_accessed_at": last_accessed_at,
    }
