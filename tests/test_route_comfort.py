"""`POST /route` uses real OSM corridor factors and says so (001 AC-2).

The explanation must never name a factor the data does not have: when Overpass
is unavailable the route still returns, with a data-gap line instead.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import comfort, main
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
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(main, "cache", Cache(str(tmp_path / "cache.db")))
    monkeypatch.setattr(
        main,
        "geocode_place",
        lambda place: (48.13, 11.57) if place == "Start" else (48.14, 11.58),
    )
    monkeypatch.setattr(
        main.mapbox, "route", lambda start, end, preference=None: FAKE_ROUTE
    )
    with TestClient(main.app) as test_client:
        yield test_client


def _post(client: TestClient, preference: str | None = "hot"):
    return client.post(
        "/route", json={"start": "Start", "end": "End", "preference": preference}
    )


def test_the_explanation_names_the_osm_corridor(client: TestClient) -> None:
    body = _post(client).json()
    text = "\n".join(body["explanation"])
    assert "Comfort data: OSM corridor" in text
    assert "shade 0.60" in text
    assert "quiet 0.80" in text
    assert "5 ways" in text


def test_shade_moves_the_score_the_way_the_preference_asks(client: TestClient) -> None:
    hot = _post(client, "hot").json()["comfort_score"]
    cloudy = _post(client, "cloudy").json()["comfort_score"]
    # Shade 0.6: +0.4 for heat/shade seekers, -0.4 for sun seekers.
    assert hot > cloudy


def test_no_osm_data_is_an_honest_gap_not_a_missing_factor(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(comfort, "corridor_factors", lambda _geometry: None)
    body = _post(client).json()
    text = "\n".join(body["explanation"])
    assert "OSM corridor unavailable" in text
    assert "data gap" in text
    assert "shade 0.60" not in text


def test_a_cache_hit_does_not_refetch_the_corridor(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    real = comfort.corridor_factors

    def counting(geometry, **kwargs):
        calls.append(1)
        return real(geometry, **kwargs)

    monkeypatch.setattr(comfort, "corridor_factors", counting)
    _post(client)
    _post(client)
    assert len(calls) == 1, "the cached response must not re-query Overpass"
