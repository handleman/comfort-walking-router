"""API tests for saved routes (spec 005, AC-1/AC-2/AC-6).

The bearer-token -> holder_id resolution is monkeypatched so tests are
hermetic (no DATABASE_URL), and the routes repository is replaced with an
in-memory fake that records save/list/recall/delete calls per holder.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import saved_routes
from app.auth import hash_token
from app.main import app as fastapi_app

_HOLDER_A = "holder-a"
_HOLDER_B = "holder-b"
_TOKEN_A = "token-a"
_TOKEN_B = "token-b"

_REQUEST: dict[str, Any] = {"origin": [52.52, 13.405], "destination": [48.135, 11.582]}
_RESPONSE: dict[str, Any] = {"distance_km": 585.0, "duration_h": 6.0}


class _FakeRoutesRepo:
    """In-memory stand-in for app.repositories.routes."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], dict[str, Any]] = {}

    def save_route(
        self, holder_id: str, route_id: str, request: Any, response: Any
    ) -> dict[str, Any]:
        row = {
            "id": route_id,
            "holder_id": holder_id,
            "request": request,
            "response": response,
        }
        self._rows[(holder_id, route_id)] = row
        return row

    def list_routes(self, holder_id: str) -> list[dict[str, Any]]:
        return [
            row for (holder, _), row in self._rows.items() if holder == holder_id
        ]

    def recall_route(self, holder_id: str, route_id: str) -> dict[str, Any] | None:
        return self._rows.get((holder_id, route_id))

    def delete_route(self, holder_id: str, route_id: str) -> bool:
        return self._rows.pop((holder_id, route_id), None) is not None


@pytest.fixture()
def fake_repo() -> _FakeRoutesRepo:
    return _FakeRoutesRepo()


@pytest.fixture()
def client(
    fake_repo: _FakeRoutesRepo, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """TestClient with auth and repository monkeypatched to fakes."""

    def fake_lookup(token_hash: str) -> str | None:
        if token_hash == hash_token(_TOKEN_A):
            return _HOLDER_A
        if token_hash == hash_token(_TOKEN_B):
            return _HOLDER_B
        return None

    monkeypatch.setattr(saved_routes, "_lookup_holder_id", fake_lookup)
    monkeypatch.setattr(saved_routes, "routes_repo", fake_repo)
    # bearer_holder 503s when DATABASE_URL is unset; tests are hermetic, so
    # pretend one is configured (auth/repo are faked below anyway).
    monkeypatch.setattr("app.db.DATABASE_URL", "postgres://test/test")
    with TestClient(fastapi_app) as test_client:
        yield test_client


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _save(client: TestClient, token: str = _TOKEN_A) -> Any:
    return client.post(
        "/saved-routes",
        json={"request": _REQUEST, "response": _RESPONSE},
        headers=_auth(token),
    )


def test_save_route_returns_201_for_bearer_holder(client: TestClient) -> None:
    response = _save(client)

    assert response.status_code == 201
    body = response.json()
    assert body["holder_id"] == _HOLDER_A
    assert body["request"] == _REQUEST
    assert body["response"] == _RESPONSE
    assert body["id"]


def test_list_returns_only_own_saved_routes(client: TestClient) -> None:
    mine = _save(client).json()
    _save(client, token=_TOKEN_B)

    response = client.get("/saved-routes", headers=_auth(_TOKEN_A))

    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert ids == [mine["id"]]


def test_recall_saved_route_returns_saved_payload(client: TestClient) -> None:
    saved = _save(client).json()

    response = client.get(f"/saved-routes/{saved['id']}", headers=_auth(_TOKEN_A))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == saved["id"]
    assert body["request"] == _REQUEST
    assert body["response"] == _RESPONSE


def test_recall_unknown_route_is_404(client: TestClient) -> None:
    response = client.get("/saved-routes/nope", headers=_auth(_TOKEN_A))

    assert response.status_code == 404


def test_recall_other_holders_route_is_404_and_leaks_no_token(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """AC-6: cross-holder recall is 404 and no bearer token is leaked."""
    saved = _save(client, token=_TOKEN_B).json()

    with caplog.at_level("DEBUG"):
        response = client.get(f"/saved-routes/{saved['id']}", headers=_auth(_TOKEN_A))

    assert response.status_code == 404
    assert _TOKEN_A not in response.text
    assert _TOKEN_B not in response.text
    assert _TOKEN_A not in str(response.request.url)
    assert _TOKEN_B not in str(response.request.url)
    assert _TOKEN_A not in caplog.text
    assert _TOKEN_B not in caplog.text


def test_delete_saved_route_removes_it(client: TestClient) -> None:
    saved = _save(client).json()

    deleted = client.delete(f"/saved-routes/{saved['id']}", headers=_auth(_TOKEN_A))
    recalled = client.get(f"/saved-routes/{saved['id']}", headers=_auth(_TOKEN_A))

    assert deleted.status_code == 204
    assert recalled.status_code == 404


def test_missing_bearer_token_is_401(client: TestClient) -> None:
    response = client.get("/saved-routes")

    assert response.status_code == 401


def test_capabilities_reports_saved_routes_when_db_configured(
    client: TestClient,
) -> None:
    """043 T1 AC-1: a configured database turns the feature on."""
    response = client.get("/capabilities")

    assert response.status_code == 200
    assert response.json() == {"saved_routes": True, "database": True}


def test_capabilities_reports_saved_routes_off_without_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """043 T1 AC-1: no DATABASE_URL -> the feature flags are false."""
    monkeypatch.setattr("app.db.DATABASE_URL", None)
    with TestClient(fastapi_app) as test_client:
        response = test_client.get("/capabilities")

    assert response.status_code == 200
    assert response.json() == {"saved_routes": False, "database": False}


def test_saved_routes_503_without_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """043 T1 AC-1: the saved-routes API keeps returning 503 with no database."""
    monkeypatch.setattr("app.db.DATABASE_URL", None)
    with TestClient(fastapi_app) as test_client:
        response = test_client.get("/saved-routes")

    assert response.status_code == 503


@pytest.mark.skipif(
    os.getenv("DATABASE_URL") is None, reason="DATABASE_URL not set"
)
def test_saved_routes_round_trip_with_db() -> None:
    """005 T7: the real API + Postgres round-trip (save → list → recall → delete).

    This runs without the fake repo/auth fixture so it exercises the actual
    holder bootstrap, repository SQL and JSON round-trip.
    """
    import uuid

    from fastapi.testclient import TestClient

    from app.main import app as real_app

    token = f"t7-{uuid.uuid4().hex}"
    headers = {"Authorization": f"Bearer {token}"}
    request = {"name": "Marienplatz, Munich"}
    response = {"name": "Marienplatz, Munich", "distance_m": 1485.0}

    with TestClient(real_app) as client:
        created = client.post(
            "/saved-routes",
            json={"request": request, "response": response},
            headers=headers,
        )
        assert created.status_code == 201, created.text
        route_id = created.json()["id"]

        listed = client.get("/saved-routes", headers=headers)
        assert listed.status_code == 200
        assert any(row["id"] == route_id for row in listed.json())

        recalled = client.get(f"/saved-routes/{route_id}", headers=headers)
        assert recalled.status_code == 200
        assert recalled.json()["request"] == request
        assert recalled.json()["response"] == response

        deleted = client.delete(f"/saved-routes/{route_id}", headers=headers)
        assert deleted.status_code == 204
        assert client.get(f"/saved-routes/{route_id}", headers=headers).status_code == 404
