"""`POST /route` uses real OSM corridor factors and says so (001 AC-2).

The explanation must never name a factor the data does not have: when Overpass
is unavailable the route still returns, with a data-gap line instead.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise
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
    # The corridor is stubbed by `tests/conftest.py::_no_overpass` (the recorded
    # 5-way corridor); do NOT enable ROUTE_FIXTURES here — it bypasses the
    # patched provider for "Start"/"End" and the route request fails upstream.
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
    hot = _post(client, "hot").json()["comfort_profile"]
    cloudy = _post(client, "cloudy").json()["comfort_profile"]
    # The fixture route starts under trees and is open after 40 %. A heat-avoider
    # must rate the shaded first segment above the open one, and the sun-seeker
    # the other way round — the whole-route mean depends on the mix, so compare
    # the same segment.
    assert hot[0]["score"] > hot[-1]["score"]
    assert cloudy[-1]["score"] > cloudy[0]["score"]


def test_no_osm_data_is_an_honest_gap_not_a_missing_factor(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(comfort, "corridor_data", lambda _geometry: None)
    body = _post(client).json()
    text = "\n".join(body["explanation"])
    assert "OSM corridor unavailable" in text
    assert "data gap" in text
    assert "shade 0.60" not in text


def test_the_comfort_profile_covers_the_route_contiguously(client: TestClient) -> None:
    body = _post(client).json()
    profile = body["comfort_profile"]
    assert isinstance(profile, list) and profile
    assert all(
        set(seg) >= {"from_m", "to_m", "score", "factor", "label"} for seg in profile
    )
    assert profile[0]["from_m"] == pytest.approx(0, abs=1)
    assert profile[-1]["to_m"] == pytest.approx(body["distance_m"], abs=1)
    for prev, seg in pairwise(profile):
        assert seg["from_m"] == pytest.approx(prev["to_m"], abs=1)
        assert seg["from_m"] - prev["to_m"] <= comfort.PROFILE_SEGMENT_M + 1
    expected = comfort.weighted_score(
        [comfort.ProfileSegment(**seg) for seg in profile]
    )
    assert body["comfort_score"] == pytest.approx(expected, abs=0.5)


def test_a_missing_profile_is_reported_as_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.comfort.corridor_data", lambda *a, **k: None)
    body = _post(client).json()
    assert body["comfort_profile"] is None
    assert isinstance(body["comfort_score"], float)
    assert "Profile: unavailable without OSM corridor data." in body["explanation"]


def test_a_cache_hit_does_not_refetch_the_corridor(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    real = comfort.corridor_data

    def counting(geometry, **kwargs):
        calls.append(1)
        return real(geometry, **kwargs)

    monkeypatch.setattr(comfort, "corridor_data", counting)
    _post(client)
    _post(client)
    assert len(calls) == 1, "the cached response must not re-query Overpass"
