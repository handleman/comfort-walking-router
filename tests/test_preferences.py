"""Tests for auto weather preference (hot-sunny matrix)."""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main
from app.cache import Cache
from app.preferences import auto_preference

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


@pytest.mark.parametrize(
    ("temperature", "cloud_cover", "expected"),
    [
        (25.0, 0, "hot"),
        (25.0, 69.9, "hot"),
        (30.0, 50, "hot"),
        (40.0, 0, "hot"),
    ],
)
def test_hot_sunny_matrix(temperature, cloud_cover, expected):
    """temp >= 25C and cloud < 70% -> 'hot'."""
    assert auto_preference(temperature, cloud_cover, "cool") == expected


@pytest.mark.parametrize(
    ("temperature", "cloud_cover", "expected"),
    [
        (25.0, 70, "cloudy"),
        (30.0, 70, "cloudy"),
        (40.0, 70, "cloudy"),
        (40.0, 100, "cloudy"),
        (10.0, 85, "cloudy"),
    ],
)
def test_overcast_matrix(temperature, cloud_cover, expected):
    """cloud >= 70% -> 'cloudy' (even when hot)."""
    assert auto_preference(temperature, cloud_cover, "cool") == expected


@pytest.mark.parametrize(
    ("temperature", "cloud_cover", "expected"),
    [
        (24.9, 0, "cool"),
        (24.9, 69.9, "cool"),
        (10.0, 50, "cool"),
        (0.0, 0, "cool"),
    ],
)
def test_cool_fallback_matrix(temperature, cloud_cover, expected):
    """temp < 25C and cloud < 70% -> caller preference."""
    assert auto_preference(temperature, cloud_cover, "cool") == expected


@pytest.mark.parametrize(
    ("temperature", "cloud_cover"),
    [
        (25.0, 70.0),
        (25.0, 70),
    ],
)
def test_exact_boundary_is_cloudy(temperature, cloud_cover):
    """temp exactly 25 with cloud exactly 70 -> 'cloudy'."""
    assert auto_preference(temperature, cloud_cover, "cool") == "cloudy"


@pytest.mark.parametrize(
    ("temperature", "cloud_cover"),
    [
        (None, 50),
        (30.0, None),
        (None, None),
    ],
)
def test_missing_data_falls_back_to_caller(temperature, cloud_cover):
    """None temperature or cloud_cover -> caller preference."""
    assert auto_preference(temperature, cloud_cover, "cool") == "cool"


def test_the_api_accepts_the_balanced_preference(client: TestClient) -> None:
    """041 T2: the shade panel's Balanced segment sends "balanced"."""
    response = client.post(
        "/route",
        json={"start": "Start", "end": "End", "preference": "balanced"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["applied_preference"] == "balanced"
    assert any("balanced" in line.lower() for line in body["explanation"])
