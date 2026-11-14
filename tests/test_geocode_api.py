"""API tests for GET /geocode and GET /geocode/reverse (spec 014, T2)."""

from fastapi.testclient import TestClient

from app import geocode_cache
from app.main import app

client = TestClient(app)

FAKE_RESULTS = [
    {
        "id": "test-1",
        "label": "Cafe, Testville",
        "lat": 52.52,
        "lng": 13.405,
        "type": "poi",
        "attribution": "© Test Provider",
    }
]


def _fake_geocoding(monkeypatch):
    """Stub the geocoding providers and empty the SQLite geocode cache."""
    monkeypatch.setattr(
        "app.geocoding.search",
        lambda q, lat, lng, limit: [dict(r) for r in FAKE_RESULTS[:limit]],
    )
    monkeypatch.setattr(
        "app.geocoding.reverse",
        lambda lat, lng: [dict(r) for r in FAKE_RESULTS],
    )
    geocode_cache.clear()


def test_geocode_returns_fake_results(monkeypatch):
    _fake_geocoding(monkeypatch)
    response = client.get("/geocode", params={"q": "cafe"})
    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"] == FAKE_RESULTS


def test_geocode_reverse_returns_fake_results(monkeypatch):
    _fake_geocoding(monkeypatch)
    response = client.get("/geocode/reverse", params={"lat": 52.52, "lng": 13.405})
    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"] == FAKE_RESULTS


def test_geocode_rejects_query_shorter_than_2_chars(monkeypatch):
    _fake_geocoding(monkeypatch)
    assert client.get("/geocode", params={"q": "c"}).status_code == 422


def test_geocode_rejects_query_longer_than_120_chars(monkeypatch):
    _fake_geocoding(monkeypatch)
    assert client.get("/geocode", params={"q": "x" * 121}).status_code == 422


def test_geocode_rejects_limit_out_of_range(monkeypatch):
    _fake_geocoding(monkeypatch)
    assert client.get("/geocode", params={"q": "cafe", "limit": 0}).status_code == 422
    assert client.get("/geocode", params={"q": "cafe", "limit": 11}).status_code == 422


def test_geocode_rejects_coords_out_of_range(monkeypatch):
    _fake_geocoding(monkeypatch)
    assert client.get("/geocode", params={"q": "cafe", "lat": 91}).status_code == 422
    assert client.get("/geocode", params={"q": "cafe", "lng": -181}).status_code == 422
    assert (
        client.get("/geocode/reverse", params={"lat": 91, "lng": 0}).status_code == 422
    )


def test_geocode_validation_422_matrix(monkeypatch):
    _fake_geocoding(monkeypatch)
    assert client.get("/geocode", params={"q": "a"}).status_code == 422
    assert client.get("/geocode", params={"q": "x" * 121}).status_code == 422
    assert client.get("/geocode", params={"q": "cafe", "limit": 0}).status_code == 422
    assert client.get("/geocode", params={"q": "cafe", "limit": 11}).status_code == 422
    assert (
        client.get("/geocode/reverse", params={"lat": 200, "lng": 0}).status_code
        == 422
    )


def test_geocode_serves_second_call_from_cache(monkeypatch) -> None:
    """The 5-minute SQLite cache: the provider fake runs once for two calls."""
    calls: list[tuple[str, float | None, float | None, int]] = []

    def counting_search(q, lat, lng, limit):
        calls.append((q, lat, lng, limit))
        return [dict(r) for r in FAKE_RESULTS[:limit]]

    monkeypatch.setattr("app.geocoding.search", counting_search)
    geocode_cache.clear()

    first = client.get("/geocode", params={"q": "cafe"})
    second = client.get("/geocode", params={"q": "cafe"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(calls) == 1
    assert first.json()["suggestions"] == FAKE_RESULTS
    assert second.json()["suggestions"] == first.json()["suggestions"]
