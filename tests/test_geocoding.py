"""Fixture-only tests for the geocoding normalization layer (spec 014, AC-8).

No live calls: every provider response is a recorded fixture injected
through `requests.get`. The tests assert the *normalized* `Suggestion`
shape, not a provider payload, so a provider's wire format may change
without touching them.
"""

from unittest.mock import patch

import pytest
import requests

from app.geocoding import (
    MAPBOX_ATTRIBUTION,
    PHOTON_ATTRIBUTION,
    Suggestion,
    reverse,
    search,
)

MAPBOX_FORWARD_FIXTURE = {
    "type": "FeatureCollection",
    "attribution": "© Mapbox © OpenStreetMap",
    "features": [
        {
            "id": "address.123",
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-74.006, 40.7128]},
            "properties": {
                "mapbox_id": "address.123",
                "feature_type": "address",
                "name": "Main Street",
                "full_address": "123 Main Street, New York, NY 10001, United States",
                "coordinates": {"latitude": 40.7128, "longitude": -74.006},
            },
        },
        {
            "id": "poi.456",
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-73.996, 40.7228]},
            "properties": {
                "mapbox_id": "poi.456",
                "feature_type": "poi",
                "name": "Oak Avenue",
                "full_address": "456 Oak Avenue, New York, NY 10001, United States",
                "coordinates": {"latitude": 40.7228, "longitude": -73.996},
            },
        },
    ],
}

MAPBOX_REVERSE_FIXTURE = {
    "type": "FeatureCollection",
    "attribution": "© Mapbox © OpenStreetMap",
    "features": [
        {
            "id": "address.789",
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-74.016, 40.7028]},
            "properties": {
                "mapbox_id": "address.789",
                "feature_type": "address",
                "name": "Pine Road",
                "full_address": "789 Pine Road, New York, NY 10001, United States",
                "coordinates": {"latitude": 40.7028, "longitude": -74.016},
            },
        }
    ],
}

PHOTON_FORWARD_FIXTURE = {
    "type": "FeatureCollection",
    "attribution": "© OpenStreetMap contributors",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [13.377702, 52.516267]},
            "properties": {
                "name": "Brandenburg Gate",
                "type": "tourism",
                "osm_id": 12345,
                "osm_type": "W",
                "city": "Berlin",
                "country": "Germany",
            },
        }
    ],
}


class _Response:
    """Minimal `requests.Response` stand-in for the mocked transport."""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            # The same exception type the real transport raises.
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


def _mock_get(payload: dict, status_code: int = 200):
    """Patch `requests.get` in the geocoding module with a fixture response."""
    return patch(
        "app.geocoding.requests.get",
        return_value=_Response(payload, status_code),
    )


def test_search_uses_mapbox_when_token_is_set(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-token")
    with _mock_get(MAPBOX_FORWARD_FIXTURE) as mock:
        results = search("Main St", 40.7128, -74.006, limit=5)

    assert mock.called
    assert len(results) == 2
    first = results[0]
    assert isinstance(first, Suggestion)
    assert first.id == "address.123"
    assert first.label == "123 Main Street, New York, NY 10001, United States"
    assert first.lat == 40.7128
    assert first.lng == -74.006
    assert first.type == "address"
    assert first.attribution == "© Mapbox © OpenStreetMap"


def test_search_sends_the_documented_mapbox_parameters(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-token")
    with _mock_get(MAPBOX_FORWARD_FIXTURE) as mock:
        search("Main St", 40.7128, -74.006, limit=5)

    url = mock.call_args.args[0]
    params = mock.call_args.kwargs["params"]
    assert url == "https://api.mapbox.com/search/geocode/v6/forward"
    assert params["q"] == "Main St"
    assert params["proximity"] == "-74.006,40.7128"
    assert params["language"] == "en"
    assert params["autocomplete"] == "true"
    assert params["types"] == "address,street,place,locality,neighborhood"
    assert params["limit"] == 5


def test_search_falls_back_to_photon_without_a_token(monkeypatch):
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)
    with _mock_get(PHOTON_FORWARD_FIXTURE) as mock:
        results = search("Brandenburg Gate", 52.516267, 13.377702, limit=5)

    assert mock.call_args.args[0] == "https://photon.komoot.io/api"
    assert len(results) == 1
    only = results[0]
    assert only.id == "W/12345"
    assert only.label == "Brandenburg Gate"
    assert only.lat == 52.516267
    assert only.lng == 13.377702
    assert only.type == "tourism"
    assert only.attribution == "© OpenStreetMap contributors"


def test_reverse_uses_mapbox_when_token_is_set(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-token")
    with _mock_get(MAPBOX_REVERSE_FIXTURE) as mock:
        results = reverse(40.7028, -74.016)

    assert mock.call_args.args[0] == "https://api.mapbox.com/search/geocode/v6/reverse"
    assert len(results) == 1
    only = results[0]
    assert only.id == "address.789"
    assert only.label == "789 Pine Road, New York, NY 10001, United States"
    assert only.lat == 40.7028
    assert only.lng == -74.016


def test_reverse_falls_back_to_photon_without_a_token(monkeypatch):
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)
    with _mock_get(PHOTON_FORWARD_FIXTURE) as mock:
        results = reverse(52.516267, 13.377702)

    assert mock.call_args.args[0] == "https://photon.komoot.io/api/reverse"
    assert len(results) == 1
    assert results[0].lat == 52.516267


def test_provider_failure_returns_no_suggestions(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-token")
    with _mock_get({}, status_code=503):
        assert search("Main St") == []


def test_empty_query_never_calls_the_provider(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-token")
    with _mock_get(MAPBOX_FORWARD_FIXTURE) as mock:
        assert search("   ") == []
    assert not mock.called


def test_attribution_falls_back_when_the_payload_omits_it(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-token")
    payload = {**MAPBOX_FORWARD_FIXTURE}
    payload.pop("attribution")
    with _mock_get(payload):
        results = search("Main St")
    assert results[0].attribution == MAPBOX_ATTRIBUTION


def test_photon_attribution_fallback(monkeypatch):
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)
    payload = {**PHOTON_FORWARD_FIXTURE}
    payload.pop("attribution")
    with _mock_get(payload):
        results = search("Brandenburg Gate")
    assert results[0].attribution == PHOTON_ATTRIBUTION


@pytest.mark.parametrize(
    ("feature", "reason"),
    [
        ({"properties": {"name": "No coordinates"}}, "missing coordinates"),
        ({"properties": {"coordinates": {"latitude": 1.0}}}, "missing longitude"),
        ({"properties": {"coordinates": {"latitude": 1.0, "longitude": 2.0}}}, "missing label"),
    ],
)
def test_incomplete_features_are_skipped(monkeypatch, feature, reason):
    monkeypatch.setenv("MAPBOX_TOKEN", "test-token")
    payload = {
        "attribution": "© Mapbox © OpenStreetMap",
        "features": [feature],
    }
    with _mock_get(payload):
        assert search("Main St") == [], reason
