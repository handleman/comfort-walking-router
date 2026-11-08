from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main
from app.cache import Cache

FAKE_ROUTE: dict[str, Any] = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[11.57, 48.13], [11.58, 48.14]],
            },
            "properties": {"distance": 1234.5, "duration": 900.0},
        }
    ],
}


@pytest.fixture()
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setattr(main, "cache", Cache(str(tmp_path / "cache.db")))
    monkeypatch.setattr(
        main,
        "geocode_place",
        lambda place: (48.13, 11.57) if place == "Start" else (48.14, 11.58),
    )
    monkeypatch.setattr(
        main.osrm,
        "route",
        lambda start, end, preference=None: FAKE_ROUTE,
    )
    with TestClient(main.app) as test_client:
        yield test_client


def _post(client: TestClient, preference: str | None = "hot"):
    return client.post(
        "/route",
        json={"start": "Start", "end": "End", "preference": preference},
    )


def test_route_matches_contract(client: TestClient) -> None:
    response = _post(client)

    assert response.status_code == 200
    body = response.json()
    assert body["geometry"] == FAKE_ROUTE["features"][0]["geometry"]
    assert body["distance_m"] == 1234.5
    assert body["duration_s"] == 900.0
    assert body["waypoints"] == [
        {"lat": 48.13, "lng": 11.57},
        {"lat": 48.14, "lng": 11.58},
    ]
    assert body["status"] == "active"
    assert body["explanation"]


def test_identical_query_hits_cache(client: TestClient) -> None:
    first = _post(client).json()
    second = _post(client).json()

    assert first == second


def test_unknown_preference_is_rejected(client: TestClient) -> None:
    response = _post(client, preference="rainy")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert "message" in body
