"""Pinned /route request contract (spec 001, task T11, AC-2).

No network: geocode_place and mapbox.route are patched with the same
patches tests/test_route_api.py uses. The `client` fixture is declared
here instead of imported from that module because a cross-test-module
import makes mypy see tests/test_route_api.py under two module names
(`test_route_api` and `tests.test_route_api`). Asserts FastAPI
validation plus the pinned response keys.
"""

import json
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


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "route.json"


def _comfort_profile_schema() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["properties"][
        "comfort_profile"
    ]


def _assert_entry_matches(entry: dict[str, Any], schema: dict[str, Any]) -> None:
    assert sorted(entry) == sorted(schema["items"]["required"])
    assert isinstance(entry["from_m"], (int, float)) and entry["from_m"] >= 0
    assert isinstance(entry["to_m"], (int, float)) and entry["to_m"] >= 0
    assert 0 <= float(entry["score"]) <= 100
    assert entry["factor"] in schema["items"]["properties"]["factor"]["enum"]
    assert isinstance(entry["label"], str) and 0 < len(entry["label"]) <= 40


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


def test_response_comfort_profile_is_array_or_null(client: TestClient) -> None:
    response = client.post(
        "/route",
        json={"start": "Start", "end": "End", "preference": "hot"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "comfort_profile" in body
    assert body["comfort_profile"] is None or isinstance(
        body["comfort_profile"], list
    )
    assert (
        "comfort_profile"
        not in json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["required"]
    )


def test_response_comfort_profile_entries_and_contiguity(client: TestClient) -> None:
    response = client.post(
        "/route",
        json={"start": "Start", "end": "End", "preference": "hot"},
    )

    assert response.status_code == 200
    body = response.json()
    if not body["comfort_profile"]:
        assert body["comfort_profile"] is not None
        return
    entries = body["comfort_profile"]
    schema = _comfort_profile_schema()
    for entry in entries:
        _assert_entry_matches(entry, schema)
    assert entries[0]["from_m"] == 0.0
    for i in range(1, len(entries)):
        assert entries[i]["from_m"] == entries[i - 1]["to_m"]
    assert entries[-1]["to_m"] == pytest.approx(body["distance_m"], abs=1.0)
