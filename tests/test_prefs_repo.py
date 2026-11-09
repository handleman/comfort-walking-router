"""Tests for the prefs repository (per-holder saved route preferences)."""

import os

import pytest

from app.db import get_connection
from app.repositories import prefs as prefs_repo

skipif_no_db = pytest.mark.skipif(
    os.getenv("DATABASE_URL") is None, reason="DATABASE_URL not set"
)

_HOLDER_A = "holder-a"
_HOLDER_B = "holder-b"


@skipif_no_db
def test_get_prefs_returns_none_when_missing():
    assert prefs_repo.get_prefs(_HOLDER_B) is None


@skipif_no_db
def test_update_prefs_upserts_existing_row():
    first = prefs_repo.update_prefs(
        _HOLDER_A, {"default_preference": "route-1"}
    )
    assert first["holder_id"] == _HOLDER_A
    assert first["default_preference"] == "route-1"

    second = prefs_repo.update_prefs(
        _HOLDER_A, {"default_preference": "route-2"}
    )
    assert second["holder_id"] == _HOLDER_A
    assert second["default_preference"] == "route-2"

    saved = prefs_repo.get_prefs(_HOLDER_A)
    assert saved is not None
    assert saved["default_preference"] == "route-2"

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM prefs WHERE holder_id = %s", (_HOLDER_A,)
        )
        (count,) = cur.fetchone()
    assert count == 1


@skipif_no_db
def test_get_prefs_scoped_to_holder():
    prefs_repo.update_prefs(_HOLDER_A, {"default_preference": "route-a"})
    prefs_repo.update_prefs(_HOLDER_B, {"default_preference": "route-b"})

    prefs_a = prefs_repo.get_prefs(_HOLDER_A)
    prefs_b = prefs_repo.get_prefs(_HOLDER_B)

    assert prefs_a is not None
    assert prefs_a["default_preference"] == "route-a"

    assert prefs_b is not None
    assert prefs_b["default_preference"] == "route-b"
