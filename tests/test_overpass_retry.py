"""Multi-mirror retry: first Overpass endpoint fails, second succeeds (039 T1)."""

from __future__ import annotations

from unittest.mock import patch

from app import comfort

URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

FEATURES = [
    {
        "type": "Feature",
        "properties": {"highway": "footway", "lit": "yes"},
        "geometry": {"type": "LineString", "coordinates": [[11.57, 48.13], [11.58, 48.14]]},
    }
]


def test_first_endpoint_fails_second_succeeds(capsys):
    calls: list[str] = []

    seen_queries: list[str] = []

    def fake_fetch(url, query):
        calls.append(url)
        seen_queries.append(query)
        if url == URLS[0]:
            raise RuntimeError("502 all query workers are busy")
        return FEATURES

    with patch.object(comfort.overpass, "fetch_overpass_features", side_effect=fake_fetch):
        result = comfort._overpass_features("[out:json];way[highway];out;")

    assert result == FEATURES
    assert calls == list(URLS[:2])
    assert seen_queries == ["[out:json];way[highway];out;"] * 2
    out = capsys.readouterr().out
    assert URLS[0] in out and "502 all query workers are busy" in out
    assert "all endpoints failed" not in out


def test_first_endpoint_fails_second_succeeds_mocked_requests():
    """Same retry, but mocking `requests` at the provider level (039 T1)."""
    from unittest.mock import MagicMock

    bad = MagicMock()
    bad.raise_for_status.side_effect = RuntimeError("502 all query workers are busy")
    good = MagicMock()
    good.json.return_value = {
        "elements": [{"type": "node", "id": 1, "lat": 48.13, "lon": 11.57, "tags": {}}]
    }

    with patch.object(comfort.overpass.requests, "get", side_effect=[bad, good]) as get:
        features = comfort._overpass_features("[out:json][timeout:40]")

    assert get.call_count == 2
    assert get.call_args_list[0].args[0] == URLS[0]
    assert get.call_args_list[1].args[0] == URLS[1]
    assert features and features[0]["properties"]["id"] == 1


def test_all_endpoints_fail_returns_none(capsys):
    with patch.object(
        comfort.overpass,
        "fetch_overpass_features",
        side_effect=RuntimeError("timeout"),
    ) as fetch:
        result = comfort._overpass_features("[out:json];way[highway];out;")

    assert result is None
    assert fetch.call_count == 3
    assert [c.args[0] for c in fetch.call_args_list] == list(URLS)
    assert "all endpoints failed" in capsys.readouterr().out


def test_all_endpoints_timeout_corridor_degrades_to_weather_only(capsys, real_corridor):
    """Timeout path: every mirror times out → corridor is None, never a 5xx."""
    import requests

    seen_timeouts: list[float] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        seen_timeouts.append(timeout)
        raise requests.exceptions.Timeout(f"timed out: {url}")

    with patch.object(requests, "get", side_effect=fake_get):
        geometry = {
            "type": "LineString",
            "coordinates": [[11.57, 48.13], [11.58, 48.14]],
        }
        assert comfort.corridor_factors(geometry) is None

    # All three mirrors were tried, in order, with the raised 90 s outer bound.
    assert seen_timeouts == [90.0, 90.0, 90.0]
    out = capsys.readouterr().out
    for url in URLS:
        assert url in out and "timed out" in out
    assert "all endpoints failed" in out
