"""AC-3: calls-vs-cache-hits INFO logging around the /route cache."""

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main
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
def client_and_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, list[tuple[float, float]]]]:
    """Client with a counted fake OSRM provider and reset cache counters."""
    calls: list[tuple[float, float]] = []
    monkeypatch.setattr(main, "cache", Cache(str(tmp_path / "cache.db")))
    monkeypatch.setattr(
        main,
        "geocode_place",
        lambda place: (48.13, 11.57) if place == "Start" else (48.14, 11.58),
    )

    def fake_route(
        start: tuple[float, float],
        end: tuple[float, float],
        preference: str | None = None,
    ) -> dict[str, Any]:
        calls.append(start)
        return FAKE_ROUTE

    monkeypatch.setattr(main.osrm, "route", fake_route)
    monkeypatch.setattr(main, "cache_hits", 0)
    monkeypatch.setattr(main, "provider_calls", 0)
    with TestClient(main.app) as test_client:
        yield test_client, calls


def _post(client: TestClient) -> None:
    response = client.post(
        "/route",
        json={"start": "Start", "end": "End", "preference": "hot"},
    )
    assert response.status_code == 200


def test_cache_miss_logs_info_and_calls_provider(
    client_and_calls: tuple[TestClient, list[tuple[float, float]]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, calls = client_and_calls

    with caplog.at_level(logging.INFO, logger="app.main"):
        _post(client)

    assert calls == [(48.13, 11.57)]
    assert main.provider_calls == 1
    assert main.cache_hits == 0
    misses = [r for r in caplog.records if "cache miss" in r.getMessage()]
    assert len(misses) == 1
    assert misses[0].levelno == logging.INFO
    assert "Start|End|hot" in misses[0].getMessage()


def test_cache_hit_logs_info_and_skips_provider(
    client_and_calls: tuple[TestClient, list[tuple[float, float]]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, calls = client_and_calls

    with caplog.at_level(logging.INFO, logger="app.main"):
        _post(client)
        _post(client)

    assert len(calls) == 1  # provider ran only for the first request
    assert main.provider_calls == 1
    assert main.cache_hits == 1
    hits = [r for r in caplog.records if "cache hit" in r.getMessage()]
    assert len(hits) == 1
    assert hits[0].levelno == logging.INFO
    assert "skipping provider" in hits[0].getMessage()
