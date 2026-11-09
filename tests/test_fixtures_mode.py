"""AC-2 (micro-step 7/7): /route works offline with ROUTE_FIXTURES=1.

The flag is read per-request inside ``app.main``, so it is enabled through
an autouse fixture instead of module-level ``os.environ`` mutation, which
would leak into every other test module imported after this one.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fixtures_mode(monkeypatch: pytest.MonkeyPatch):
    """Enable fixtures mode for this module only; no env leakage."""
    monkeypatch.setenv("ROUTE_FIXTURES", "1")


def test_known_place_returns_200_with_route_data():
    response = client.post(
        "/route", json={"start": "Central Park", "end": "Times Square"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["distance_m"] > 0
    assert data["duration_s"] > 0
    assert data["waypoints"]
    # /route returns the first feature's geometry (LineString), matching the
    # live-mode contract asserted in tests/test_route_api.py.
    assert data["geometry"]["type"] == "LineString"


def test_unknown_place_returns_404():
    response = client.post(
        "/route", json={"start": "Definitely Not A Real Place", "end": "Times Square"}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
