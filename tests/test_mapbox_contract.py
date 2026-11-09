"""Contract test: Mapbox fixture properties -> score_comfort -> contracts/route.json.

Loads ``tests/fixtures/mapbox-single.json``, runs the route's feature
properties through ``score_comfort``, builds a response dict, and validates
the required fields and types against ``contracts/route.json``.
"""

import importlib
import json
import logging
import math
import pkgutil
from datetime import datetime
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

TESTS_DIR = Path(__file__).resolve().parent
FIXTURE_PATH = TESTS_DIR / "fixtures" / "mapbox-single.json"
CONTRACT_PATH = TESTS_DIR.parent / "contracts" / "route.json"

JSON_TYPE_TO_PYTHON = {
    "string": str,
    "number": (int, float),
    "array": list,
    "object": dict,
    "boolean": bool,
}


def _import_app_modules():
    """Yield every importable module under the app package."""
    try:
        app = importlib.import_module("app")
    except ImportError:
        return
    yield app
    for info in pkgutil.walk_packages(app.__path__, prefix="app."):
        try:
            yield importlib.import_module(info.name)
        except ImportError:  # pragma: no cover - skip modules with import side effects
            logger.debug("Skipping module %s with import errors", info.name)
            continue


def _load_score_comfort():
    for module in _import_app_modules():
        if hasattr(module, "score_comfort"):
            return module.score_comfort
    raise ImportError("score_comfort not found anywhere under app/")


def feature_properties(payload):
    """Flatten the Mapbox route into feature-style properties for scoring."""
    route = payload["routes"][0]
    return {
        "distance": route["distance"],
        "duration": route["duration"],
        "distance_m": float(route["distance"]),
        "duration_s": float(route["duration"]),
        "geometry": route["geometry"],
        "waypoints": [
            {"lat": wp["location"][1], "lng": wp["location"][0]}
            for wp in payload["waypoints"]
        ],
    }


def build_response(props, comfort_score):
    """Build a response dict shaped like contracts/route.json RouteResponse."""
    return {
        "id": "mapbox-single",
        "name": "Torstraße to Rosenthaler Platz",
        "description": "Walking route built from the mapbox-single fixture",
        "waypoints": props["waypoints"],
        "status": "active",
        "timestamp": "2024-05-01T12:00:00Z",
        "comfort_score": comfort_score,
        "explanation": ["Comfort score computed from Mapbox feature properties"],
        "geometry": props["geometry"],
        "distance_m": props["distance_m"],
        "duration_s": props["duration_s"],
        "applied_preference": "cloudy",
        "preference_source": "auto",
        "weather": {"summary": "clear"},
    }


@pytest.fixture(scope="session")
def score_comfort():
    return _load_score_comfort()


@pytest.fixture()
def fixture_payload():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_score_comfort_returns_finite_number(fixture_payload, score_comfort):
    score = score_comfort(feature_properties(fixture_payload))
    assert isinstance(score, (int, float)) and not isinstance(score, bool)
    assert math.isfinite(score)


def test_response_has_all_required_fields(fixture_payload, contract, score_comfort):
    props = feature_properties(fixture_payload)
    response = build_response(props, score_comfort(props))
    for field in contract["required"]:
        assert field in response, f"missing required field: {field}"


def test_response_field_types_match_contract(fixture_payload, contract, score_comfort):
    props = feature_properties(fixture_payload)
    response = build_response(props, score_comfort(props))
    for field, spec in contract["properties"].items():
        if field not in response or "type" not in spec:
            logger.debug("Skipping contract field %s with no type spec", field)
            continue
        value = response[field]
        expected = JSON_TYPE_TO_PYTHON[spec["type"]]
        assert isinstance(value, expected), f"{field}: expected {spec['type']}"
        if spec["type"] == "number":
            assert not isinstance(value, bool), f"{field}: bool is not a number"
        if "enum" in spec:
            assert value in spec["enum"], f"{field}: {value!r} not in enum"


def test_response_geometry_and_waypoints_match_contract(
    fixture_payload, contract, score_comfort
):
    props = feature_properties(fixture_payload)
    response = build_response(props, score_comfort(props))
    linestring = contract["$defs"]["LineString"]
    assert response["geometry"]["type"] == linestring["properties"]["type"]["const"]
    for coord in response["geometry"]["coordinates"]:
        assert isinstance(coord, list) and len(coord) == 2
        assert all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in coord
        )
    waypoint_spec = contract["properties"]["waypoints"]["items"]
    for waypoint in response["waypoints"]:
        for field in waypoint_spec["required"]:
            assert field in waypoint, f"waypoint missing {field}"
            assert isinstance(waypoint[field], (int, float)) and not isinstance(
                waypoint[field], bool
            ), f"waypoint.{field} must be a number"


def test_response_numeric_minimums_and_timestamp(
    fixture_payload, contract, score_comfort
):
    props = feature_properties(fixture_payload)
    response = build_response(props, score_comfort(props))
    assert response["distance_m"] >= contract["properties"]["distance_m"]["minimum"]
    assert response["duration_s"] >= contract["properties"]["duration_s"]["minimum"]
    parsed = datetime.fromisoformat(response["timestamp"])
    assert parsed.tzinfo is not None
