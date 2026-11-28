"""Corridor comfort factors from OSM (001 AC-2).

The scorer used to name shade/quiet factors it never had: `fetch_overpass_features`
had no caller. These tests pin the join — bbox, query, normalization, the
fixture path and the failure path — without touching the network.
"""

from __future__ import annotations

import pytest

from app import comfort, fixtures
from app.providers import overpass


@pytest.fixture(autouse=True)
def _allow_real_corridor(real_corridor):
    """Use the real `corridor_factors`; the fetch is stubbed per test."""


def test_the_bbox_covers_the_route_with_a_margin():
    south, west, north, east = comfort.corridor_bbox(
        {"coordinates": [[11.57, 48.13], [11.58, 48.14]]}, margin_m=60
    )
    assert south < 48.13 and north > 48.14
    assert west < 11.57 and east > 11.58
    # 60 m is ~0.00054 degrees of latitude.
    assert north - 48.14 == pytest.approx(0.00054, abs=1e-5)


def test_the_query_asks_for_paths_and_trees_in_the_box():
    query = comfort.overpass_query((48.1, 11.5, 48.2, 11.6))
    assert "way[highway](48.1,11.5,48.2,11.6)" in query
    assert "node[natural=tree](48.1,11.5,48.2,11.6)" in query
    assert "out tags" in query


def test_counts_become_normalized_factors():
    factors = comfort.factors_from_counts(
        overpass.count_features(fixtures.recorded_corridor_elements())
    )
    assert factors["osm_ways"] == 5
    assert factors["shade_factor"] == 0.6  # (2 trees + 1 grass) / 5 ways
    assert factors["quiet_factor"] == 0.8  # footway 2 + path 1 + residential 1
    assert factors["lit_share"] == 0.6
    assert factors["highway"] == "footway"
    assert factors["source"] == "osm-corridor"


def test_a_corridor_with_no_mapped_ways_has_no_factors():
    factors = comfort.factors_from_counts({"highway_breakdown": {}})
    assert factors["shade_factor"] is None
    assert factors["quiet_factor"] is None
    assert factors["osm_ways"] == 0


def test_shade_is_capped_at_one():
    counts = {"highway_breakdown": {"footway": 1}, "trees": 99, "grass": 5}
    assert comfort.factors_from_counts(counts)["shade_factor"] == 1.0


def test_the_corridor_uses_the_recorded_fixtures_in_fixtures_mode(monkeypatch):
    monkeypatch.setenv("ROUTE_FIXTURES", "1")

    def boom(*_args, **_kwargs):  # pragma: no cover - must not run
        raise AssertionError("fixtures mode must not call Overpass")

    monkeypatch.setattr(overpass, "fetch_overpass_features", boom)
    factors = comfort.corridor_factors({"coordinates": [[11.57, 48.13], [11.58, 48.14]]})
    assert factors and factors["osm_ways"] == 5


def test_a_failed_lookup_is_a_data_gap_not_a_failed_route(monkeypatch):
    monkeypatch.setenv("ROUTE_FIXTURES", "0")

    def down(*_args, **_kwargs):
        raise overpass.requests.RequestException("overpass down")

    monkeypatch.setattr(overpass, "fetch_overpass_features", down)
    assert comfort.corridor_factors({"coordinates": [[11.57, 48.13], [11.58, 48.14]]}) is None


def test_geojson_from_the_provider_is_counted(monkeypatch):
    monkeypatch.setenv("ROUTE_FIXTURES", "0")
    features = [
        {
            "geometry": {"type": "LineString", "coordinates": []},
            "properties": {"highway": "footway", "lit": "yes"},
        },
        {"geometry": {"type": "Point", "coordinates": [11.5, 48.1]}, "properties": {"natural": "tree"}},
    ]
    monkeypatch.setattr(overpass, "fetch_overpass_features", lambda *a, **k: features)
    factors = comfort.corridor_factors({"coordinates": [[11.57, 48.13], [11.58, 48.14]]})
    assert factors["osm_ways"] == 1
    assert factors["osm_trees"] == 1
    assert factors["lit_share"] == 1.0


def test_a_route_without_coordinates_has_no_factors():
    assert comfort.corridor_factors({"coordinates": []}) is None


def test_corridor_join_has_a_deadline_and_degrades_to_weather(monkeypatch):
    """043 AC-3: a slow OSM corridor must not hold /route past the gateway."""
    import time

    from app import main

    geometry = {"type": "LineString", "coordinates": []}
    monkeypatch.setattr(main, "CORRIDOR_JOIN_BUDGET_SECONDS", 0.05)
    monkeypatch.setattr(
        main.comfort,
        "corridor_data",
        lambda geometry: (time.sleep(0.5), None)[1],
    )
    started = time.monotonic()
    assert main._corridor_with_deadline(geometry) is None
    assert time.monotonic() - started < 0.4


def test_corridor_join_returns_the_fast_result(monkeypatch):
    from app import main

    geometry = {"type": "LineString", "coordinates": []}
    payload = {"factors": {"quiet_factor": 0.8}}
    monkeypatch.setattr(main.comfort, "corridor_data", lambda g: payload)
    assert main._corridor_with_deadline(geometry) == payload
