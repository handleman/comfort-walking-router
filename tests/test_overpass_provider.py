from typing import Any

import pytest

from app.providers.overpass import fetch_overpass_features


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


def test_fetch_overpass_features_passes_through_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    geometry = {"type": "Polygon", "coordinates": [[[11.57, 48.13], [11.58, 48.14], [11.59, 48.13], [11.57, 48.13]]]}
    payload = {
        "features": [
            {"geometry": geometry, "properties": {"id": 123}},
        ],
        "type": "FeatureCollection",
    }
    
    captured = {}
    
    def capture_get(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeResponse(payload)
    
    monkeypatch.setattr(
        "app.providers.overpass.requests.get",
        capture_get,
    )

    result = fetch_overpass_features("http://overpass-api.de/api/interpreter", query="[out:json][timeout:10] area(way[highway~\".*\"])[](node); out;", user_agent="TestAgent/1.0")

    assert len(result) == 1
    assert result[0]["geometry"] == geometry
    assert result[0]["properties"]["id"] == 123
    # Verify User-Agent header was passed
    headers = captured["kwargs"].get("headers", {})
    assert "User-Agent" in headers
    assert headers["User-Agent"] == "TestAgent/1.0"
    # Verify timeout was passed
    params = captured["kwargs"].get("params", {})
    assert "timeout" in params
    assert params["timeout"] == 10
