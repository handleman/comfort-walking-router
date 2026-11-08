"""Tests for the Open-Meteo weather provider (offline, via test doubles)."""

from typing import Any

import pytest
import requests

from app.providers.open_meteo import USER_AGENT, OpenMeteoProvider


class FakeResponse:
    """Minimal requests.Response test double."""

    def __init__(self, json_data: Any, status_code: int = 200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self) -> Any:
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def test_fetch_current_returns_temperature_and_cloud_cover(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeResponse(
        {"current": {"temperature_2m": 27.0, "cloud_cover": 10}},
    )
    captured: dict[str, Any] = {}

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        return fake

    monkeypatch.setattr(requests, "get", fake_get)

    result = OpenMeteoProvider().fetch_current(52.52, 13.41)

    assert result == {"temperature": 27.0, "cloud_cover": 10}
    assert captured["headers"] == {"User-Agent": USER_AGENT}


def test_fetch_current_passes_user_agent_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeResponse(
        {"current": {"temperature_2m": 20.0, "cloud_cover": 50}},
    )
    captured: dict[str, Any] = {}

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        captured["kwargs"] = kwargs
        return fake

    monkeypatch.setattr(requests, "get", fake_get)

    OpenMeteoProvider().fetch_current(52.52, 13.41)

    kwargs = captured["kwargs"]
    assert kwargs["headers"]["User-Agent"] == USER_AGENT
    assert kwargs["timeout"] == 15


def test_fetch_current_returns_none_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        requests, "get", lambda url, **kwargs: FakeResponse({}, status_code=500)
    )

    assert OpenMeteoProvider().fetch_current(52.52, 13.41) is None


def test_fetch_current_returns_none_on_request_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        raise requests.RequestException("connection error")

    monkeypatch.setattr("app.providers.open_meteo.requests.get", fake_get)

    assert OpenMeteoProvider().fetch_current(52.52, 13.41) is None
