"""Tests for saved-route repository (save/list/recall/delete, holder-scoped)."""

import os
import uuid

import pytest

from app.repositories import routes as routes_repo

skipif_no_db = pytest.mark.skipif(
    os.getenv("DATABASE_URL") is None, reason="DATABASE_URL not set"
)

_HOLDER_A = "holder-a"
_HOLDER_B = "holder-b"

_REQUEST = {"origin": [52.52, 13.405], "destination": [48.135, 11.582]}
_RESPONSE = {"distance_km": 585.0, "duration_h": 6.0}


def _unique_route_id() -> str:
    return str(uuid.uuid4())


@skipif_no_db
def test_save_route_returns_scoped_row():
    route_id = _unique_route_id()
    saved = routes_repo.save_route(_HOLDER_A, route_id, _REQUEST, _RESPONSE)
    try:
        assert saved["id"] == route_id
        assert saved["holder_id"] == _HOLDER_A
        assert saved["request"] == _REQUEST
        assert saved["response"] == _RESPONSE
        assert saved["created_at"] is not None
        assert saved["last_accessed_at"] is not None
    finally:
        routes_repo.delete_route(_HOLDER_A, route_id)


@skipif_no_db
def test_save_route_upserts_same_holder():
    route_id = _unique_route_id()
    try:
        first = routes_repo.save_route(_HOLDER_A, route_id, _REQUEST, _RESPONSE)
        updated = routes_repo.save_route(
            _HOLDER_A, route_id, _REQUEST, {"distance_km": 600.0}
        )
        assert updated["id"] == first["id"]
        assert updated["response"] == {"distance_km": 600.0}
        assert len(routes_repo.list_routes(_HOLDER_A)) >= 1
    finally:
        routes_repo.delete_route(_HOLDER_A, route_id)


@skipif_no_db
def test_list_routes_scoped_to_holder():
    route_id = _unique_route_id()
    other_id = _unique_route_id()
    try:
        routes_repo.save_route(_HOLDER_A, route_id, _REQUEST, _RESPONSE)
        routes_repo.save_route(_HOLDER_B, other_id, _REQUEST, _RESPONSE)

        holder_a_ids = {row["id"] for row in routes_repo.list_routes(_HOLDER_A)}
        holder_b_ids = {row["id"] for row in routes_repo.list_routes(_HOLDER_B)}

        assert route_id in holder_a_ids
        assert other_id not in holder_a_ids
        assert other_id in holder_b_ids
        assert route_id not in holder_b_ids
    finally:
        routes_repo.delete_route(_HOLDER_A, route_id)
        routes_repo.delete_route(_HOLDER_B, other_id)


@skipif_no_db
def test_recall_route_refreshes_and_returns_row():
    route_id = _unique_route_id()
    try:
        routes_repo.save_route(_HOLDER_A, route_id, _REQUEST, _RESPONSE)
        recalled = routes_repo.recall_route(_HOLDER_A, route_id)
        assert recalled is not None
        assert recalled["id"] == route_id
        assert recalled["holder_id"] == _HOLDER_A
        assert recalled["request"] == _REQUEST
    finally:
        routes_repo.delete_route(_HOLDER_A, route_id)


@skipif_no_db
def test_recall_route_wrong_holder_is_404_none():
    route_id = _unique_route_id()
    try:
        routes_repo.save_route(_HOLDER_A, route_id, _REQUEST, _RESPONSE)
        assert routes_repo.recall_route(_HOLDER_B, route_id) is None
        # Still retrievable by the owning holder afterwards.
        assert routes_repo.recall_route(_HOLDER_A, route_id) is not None
    finally:
        routes_repo.delete_route(_HOLDER_A, route_id)


@skipif_no_db
def test_recall_route_missing_is_404_none():
    assert routes_repo.recall_route(_HOLDER_A, _unique_route_id()) is None


@skipif_no_db
def test_recall_route_invalid_uuid_is_404_none():
    assert routes_repo.recall_route(_HOLDER_A, "not-a-uuid") is None


@skipif_no_db
def test_delete_route_removes_only_for_holder():
    route_id = _unique_route_id()
    routes_repo.save_route(_HOLDER_A, route_id, _REQUEST, _RESPONSE)

    # Wrong holder cannot delete (404 semantics).
    assert routes_repo.delete_route(_HOLDER_B, route_id) is False
    assert routes_repo.recall_route(_HOLDER_A, route_id) is not None

    assert routes_repo.delete_route(_HOLDER_A, route_id) is True
    assert routes_repo.recall_route(_HOLDER_A, route_id) is None
    assert routes_repo.delete_route(_HOLDER_A, route_id) is False


@skipif_no_db
def test_delete_route_missing_is_404_false():
    assert routes_repo.delete_route(_HOLDER_A, _unique_route_id()) is False
