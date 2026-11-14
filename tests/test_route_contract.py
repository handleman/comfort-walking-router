"""Pinned /route request contract (spec 001, task T11, AC-2).

No network: geocode_place and mapbox.route are patched with the same
patches tests/test_route_api.py uses. The `client` fixture is declared
here instead of imported from that module because a cross-test-module
import makes mypy see tests/test_route_api.py under two module names
(`test_route_api` and `tests.test_route_api`). Asserts FastAPI
validation plus the pinned response keys.
"""

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
        main.mapbox,
        "route",
        lambda start, end, preference=None: FAKE_ROUTE,
    )
    with TestClient(main.app) as test_client:
        yield test_client


def test_unknown_preference_returns_422(client: TestClient) -> None:
    response = client.post(
        "/route",
        json={"start": "Start", "end": "End", "preference": "rainy"},
    )

    assert response.status_code == 422


def test_missing_start_returns_422(client: TestClient) -> None:
    response = client.post("/route", json={"end": "End", "preference": "hot"})

    assert response.status_code == 422


def test_valid_request_returns_contract_keys(client: TestClient) -> None:
    response = client.post(
        "/route",
        json={"start": "Start", "end": "End", "preference": "hot"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "geometry" in body
    assert "comfort_score" in body
    assert "explanation" in body
