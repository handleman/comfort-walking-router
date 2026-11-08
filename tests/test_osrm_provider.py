from typing import Any

import pytest

from app.providers.osrm import OSRMProvider


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


def test_route_passes_through_osrm_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    geometry = {"type": "LineString", "coordinates": [[11.57, 48.13], [11.58, 48.14]]}
    payload = {
        "routes": [
            {"geometry": geometry, "distance": 1234.5, "duration": 900.0},
        ]
    }
    monkeypatch.setattr(
        "app.providers.osrm.requests.get",
        lambda *args, **kwargs: FakeResponse(payload),
    )

    result = OSRMProvider().route((48.13, 11.57), (48.14, 11.58), preference="hot")

    assert result["features"][0]["geometry"] == geometry
    assert result["features"][0]["properties"] == {
        "distance": 1234.5,
        "duration": 900.0,
    }
