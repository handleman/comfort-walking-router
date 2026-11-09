import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main
from app.cache import Cache

os.environ.setdefault("MAPBOX_TOKEN", "test-dummy-mapbox-token")

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
        main.mapbox,
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
    assert body["comfort_score"] is not None
    assert isinstance(body["comfort_score"], float)
    assert body["comfort_score"] != 50.0
    explanation_str = "\n".join(body["explanation"])
    assert "comfort factor" in explanation_str.lower()


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


def test_comfort_score_differs_by_preference(client: TestClient) -> None:
    hot_response = _post(client, preference="hot")
    cloudy_response = _post(client, preference="cloudy")

    assert hot_response.status_code == 200
    assert cloudy_response.status_code == 200

    hot_body = hot_response.json()
    cloudy_body = cloudy_response.json()

    assert hot_body["comfort_score"] != cloudy_body["comfort_score"]


def test_explanation_lists_applied_factors(client: TestClient) -> None:
    hot_response = _post(client, preference="hot")
    cloudy_response = _post(client, preference="cloudy")

    assert hot_response.status_code == 200
    assert cloudy_response.status_code == 200

    hot_body = hot_response.json()
    cloudy_body = cloudy_response.json()

    hot_explanation = "\n".join(hot_body["explanation"])
    cloudy_explanation = "\n".join(cloudy_body["explanation"])

    assert "shade factor" in hot_explanation.lower()
    assert "sun factor" in hot_explanation.lower()
    assert "sun factor" in cloudy_explanation.lower()
    assert "shade factor" in cloudy_explanation.lower()

