"""Tests for weather-driven preference selection on POST /route."""

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

WEATHER_HOT_SUNNY: dict[str, Any] = {
    "temperature": 30.2,
    "cloud_cover": 15.0,
    "wind_speed": 2.5,
}
WEATHER_OVERCAST: dict[str, Any] = {
    "temperature": 17.5,
    "cloud_cover": 88.0,
    "wind_speed": 4.0,
}


def _fake_auto_preference(
    weather: dict[str, Any] | float | None,
    cloud_cover: float | None = None,
    caller_preference: str | None = None,
) -> str | None:
    """Dict-shaped stand-in for app.preferences.auto_preference.

    main.route calls auto_preference(weather) with the fetched payload, so
    mirror the module thresholds: hot at >= 25C with cloud < 70%, cloudy at
    cloud >= 70%, otherwise fall back to the caller's preference.
    """
    if isinstance(weather, dict):
        temperature = weather.get("temperature")
        cloud_cover = weather.get("cloud_cover")
    else:
        temperature = weather
    if temperature is None or cloud_cover is None:
        return caller_preference
    if temperature >= 25.0 and cloud_cover < 70.0:
        return "hot"
    if cloud_cover >= 70.0:
        return "cloudy"
    return caller_preference


class WeatherState:
    """Payload served by the faked WeatherCache and what was written to it."""

    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None
        self.writes: list[tuple[tuple[float, float], dict[str, Any]]] = []


@pytest.fixture()
def weather_state() -> WeatherState:
    return WeatherState()


@pytest.fixture()
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    weather_state: WeatherState,
) -> Iterator[TestClient]:
    class FakeWeatherCache:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def get(self, _midpoint: tuple[float, float]) -> dict[str, Any] | None:
            return weather_state.payload

        def set(
            self, midpoint: tuple[float, float], data: dict[str, Any]
        ) -> None:
            weather_state.writes.append((midpoint, data))

    monkeypatch.setattr(main, "cache", Cache(str(tmp_path / "cache.db")))
    monkeypatch.setattr(
        main,
        "geocode_place",
        lambda place: (48.13, 11.57) if place == "Start" else (48.14, 11.58),
    )
    monkeypatch.setattr(
        main.osrm,
        "route",
        lambda start, end, preference=None: FAKE_ROUTE,
    )
    monkeypatch.setattr(main, "WeatherCache", FakeWeatherCache)
    monkeypatch.setattr(main, "auto_preference", _fake_auto_preference)
    with TestClient(main.app) as test_client:
        yield test_client


def _post(client: TestClient, preference: str | None = None):
    return client.post(
        "/route",
        json={"start": "Start", "end": "End", "preference": preference},
    )


def test_hot_sunny_weather_applies_hot_automatically(
    client: TestClient, weather_state: WeatherState
) -> None:
    weather_state.payload = dict(WEATHER_HOT_SUNNY)

    response = _post(client)

    assert response.status_code == 200
    body = response.json()
    assert body["applied_preference"] == "hot"
    assert body["preference_source"] == "auto"
    assert body["weather"] == WEATHER_HOT_SUNNY


def test_overcast_weather_applies_cloudy_automatically(
    client: TestClient, weather_state: WeatherState
) -> None:
    weather_state.payload = dict(WEATHER_OVERCAST)

    response = _post(client)

    assert response.status_code == 200
    body = response.json()
    assert body["applied_preference"] == "cloudy"
    assert body["preference_source"] == "auto"
    assert body["weather"] == WEATHER_OVERCAST


def test_manual_preference_overrides_weather(
    client: TestClient, weather_state: WeatherState
) -> None:
    weather_state.payload = dict(WEATHER_HOT_SUNNY)

    response = _post(client, preference="cloudy")

    assert response.status_code == 200
    body = response.json()
    assert body["applied_preference"] == "cloudy"
    assert body["preference_source"] == "manual"


def test_open_meteo_failure_keeps_manual_preference(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingOpenMeteo:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def fetch(self, _midpoint: tuple[float, float]) -> dict[str, Any]:
            raise RuntimeError("open-meteo unavailable")

    monkeypatch.setattr(main, "OpenMeteoProvider", FailingOpenMeteo)

    response = _post(client, preference="hot")

    assert response.status_code == 200
    body = response.json()
    assert body["applied_preference"] == "hot"
    assert body["preference_source"] == "manual"
    assert body["weather"] is None
