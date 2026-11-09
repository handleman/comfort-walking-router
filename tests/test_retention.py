"""Tests for the retention sweep (spec 005, T7 / AC-7)."""

import json
import os
import uuid

import pytest

from app.db import get_connection
from app.repositories.prefs import get_prefs, update_prefs
from app.repositories.routes import delete_route, list_routes, save_route
from app.retention import sweep_expired_routes

skipif_no_db = pytest.mark.skipif(
    os.getenv("DATABASE_URL") is None, reason="DATABASE_URL not set"
)

_HOLDER_A = "holder-a"
_HOLDER_B = "holder-b"


@pytest.fixture
def route_request() -> dict:
    return {"from": "52.52,13.405", "to": "48.8566,2.3522"}


@pytest.fixture
def route_response() -> dict:
    return {"distance_m": 878000, "duration_s": 28800}


@skipif_no_db
def test_sweep_deletes_route_older_than_90_days(
    route_request: dict, route_response: dict
):
    route_id = str(uuid.uuid4())
    save_route(_HOLDER_A, route_id, route_request, route_response)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE routes SET last_accessed_at = NOW() - INTERVAL '91 days' "
            "WHERE holder_id = %s AND id = %s",
            (_HOLDER_A, route_id),
        )

    deleted = sweep_expired_routes()
    assert deleted >= 1

    assert list_routes(_HOLDER_A) == []

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM routes WHERE holder_id = %s AND id = %s",
            (_HOLDER_A, route_id),
        )
        (count,) = cur.fetchone()
    assert count == 0

    delete_route(_HOLDER_A, route_id)
    assert json.dumps(route_request) is not None
    update_prefs(_HOLDER_A, {"default_preference": route_id})
    assert get_prefs(_HOLDER_A) is not None


@skipif_no_db
def test_sweep_keeps_route_accessed_within_90_days(
    route_request: dict, route_response: dict
):
    route_id = str(uuid.uuid4())
    save_route(_HOLDER_A, route_id, route_request, route_response)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE routes SET last_accessed_at = NOW() - INTERVAL '89 days' "
            "WHERE holder_id = %s AND id = %s",
            (_HOLDER_A, route_id),
        )

    sweep_expired_routes()

    routes = list_routes(_HOLDER_A)
    assert route_id in [r["id"] for r in routes]

    delete_route(_HOLDER_A, route_id)


@skipif_no_db
def test_sweep_preserves_prefs():
    saved = {"default_preference": "distance"}
    update_prefs(_HOLDER_B, saved)

    sweep_expired_routes()

    prefs = get_prefs(_HOLDER_B)
    assert prefs is not None
    assert prefs["default_preference"] == saved["default_preference"]


@skipif_no_db
def test_sweep_returns_deleted_count():
    holder = "holder-count"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM routes WHERE last_accessed_at < NOW() - INTERVAL '90 days'")
        for i in range(2):
            cur.execute(
                "INSERT INTO routes (id, holder_id, request, response, last_accessed_at) "
                "VALUES (%s, %s, %s, %s, NOW() - INTERVAL '91 days')",
                (str(uuid.uuid4()), holder, json.dumps({"i": i}), json.dumps({})),
            )

    deleted = sweep_expired_routes()
    assert deleted == 2

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM routes WHERE holder_id = %s", (holder,))
        (count,) = cur.fetchone()
    assert count == 0
