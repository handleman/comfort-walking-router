"""Holder registry (005, ADR-007): a token hash *is* the holder id.

There are no accounts. The first request carrying a bearer token registers that
token's hash as a holder; every saved route and preference hangs off it. The
table is `holders(token_hash)` (migration 0001) and `routes.holder_id` /
`prefs.holder_id` are foreign keys to it, so a holder must exist before anything
can be saved — which is why this is an upsert, not a lookup.

Before 2026-11-15 nothing created these rows and the API resolved the holder
against a `tokens` table that no migration creates, so the whole feature 401'd
against a live database while every test skipped for lack of DATABASE_URL.
"""

from __future__ import annotations

from app.db import get_connection

_ENSURE = """
INSERT INTO holders (token_hash) VALUES (%s)
ON CONFLICT (token_hash) DO NOTHING
"""


def ensure_holder(token_hash: str) -> str:
    """Register the holder if it is new; return its id (the token hash)."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(_ENSURE, (token_hash,))
    return token_hash


def exists(token_hash: str) -> bool:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM holders WHERE token_hash = %s", (token_hash,))
        return cur.fetchone() is not None
