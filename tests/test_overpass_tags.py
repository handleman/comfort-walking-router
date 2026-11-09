"""Tests for lit tag extraction from the overpass-lit.json fixture (spec 006, T1)."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.providers.overpass import count_features, fetch_overpass_features

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "overpass-lit.json"


def load_fixture_elements() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data["elements"]


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


def test_count_features_lit_ways_only_counts_lit_yes() -> None:
    elements = load_fixture_elements()

    counts = count_features(elements)

    # ways 2001 (lit=yes) and 2002 (lit=no) and 2003 (no lit tag): only 2001 counts
    assert counts["lit_ways"] == 1


def test_count_features_highway_breakdown_from_fixture() -> None:
    elements = load_fixture_elements()

    counts = count_features(elements)

    assert counts["highway_breakdown"] == {"street_lamp": 3, "residential": 3}
    assert counts["trees"] == 0
    assert counts["grass"] == 0
    assert counts["quiet_highways"] == 0


def test_fetch_overpass_features_exposes_lit_tags_in_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"elements": load_fixture_elements(), "version": 0.6}

    monkeypatch.setattr(
        "app.providers.overpass.requests.get",
        lambda *args, **kwargs: FakeResponse(payload),
    )

    features = fetch_overpass_features(
        "http://overpass-api.de/api/interpreter", user_agent="TestAgent/1.0"
    )

    assert len(features) == 6

    lit_by_id = {
        props["id"]: props.get("lit")
        for props in (f["properties"] for f in features)
        if "id" in props
    }
    assert lit_by_id == {
        1001: "yes",
        1002: "no",
        1003: None,
        2001: "yes",
        2002: "no",
        2003: None,
    }

    # nodes become Points with lit tags preserved; ways become empty LineStrings
    node_features = [f for f in features if f["geometry"]["type"] == "Point"]
    way_features = [f for f in features if f["geometry"]["type"] == "LineString"]
    assert len(node_features) == 3
    assert len(way_features) == 3
    assert node_features[0]["geometry"]["coordinates"] == [13.405, 52.52]
    assert way_features[0]["geometry"]["coordinates"] == []


HIGHWAY_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "overpass-highway.json"


def load_highway_fixture_elements() -> list[dict[str, Any]]:
    with HIGHWAY_FIXTURE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data["elements"]


def test_count_features_highway_class_breakdown_from_highway_fixture() -> None:
    elements = load_highway_fixture_elements()

    counts = count_features(elements)

    # one way per class: primary, secondary, trunk, residential, footway
    assert counts["highway_breakdown"] == {
        "primary": 1,
        "secondary": 1,
        "trunk": 1,
        "residential": 1,
        "footway": 1,
    }


def test_count_features_highway_fixture_quiet_and_other_counts() -> None:
    elements = load_highway_fixture_elements()

    counts = count_features(elements)

    # way 1005 (highway=footway, foot=yes) is the only quiet highway;
    # the highway fixture carries no lit tags, trees or grass
    assert counts["quiet_highways"] == 1
    assert counts["lit_ways"] == 0
    assert counts["trees"] == 0
    assert counts["grass"] == 0


def test_fetch_overpass_features_exposes_highway_class_in_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"elements": load_highway_fixture_elements(), "version": 0.6}

    monkeypatch.setattr(
        "app.providers.overpass.requests.get",
        lambda *args, **kwargs: FakeResponse(payload),
    )

    features = fetch_overpass_features(
        "http://overpass-api.de/api/interpreter", user_agent="TestAgent/1.0"
    )

    assert len(features) == 5
    assert all(f["geometry"]["type"] == "LineString" for f in features)

    highway_by_name = {
        props["name"]: props["highway"]
        for props in (f["properties"] for f in features)
        if "name" in props and "highway" in props
    }
    assert highway_by_name == {
        "Primary Avenue": "primary",
        "Secondary Street": "secondary",
        "Trunk Boulevard": "trunk",
        "Residential Lane": "residential",
        "Footway Path": "footway",
    }
