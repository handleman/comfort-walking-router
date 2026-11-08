"""Tests for app.weather_cache.WeatherCache."""

import json
import sqlite3

import pytest

from app.weather_cache import WeatherCache


@pytest.fixture()
def cache(tmp_path):
    """Return a WeatherCache backed by a temporary database."""
    return WeatherCache(db_path=str(tmp_path / "weather_cache.db"), ttl_seconds=1800)


def test_set_get_round_trip_returns_identical_data(cache):
    payload = {"temperature": 21.5, "code": "clear"}
    cache.set(40.12, -73.98, payload)
    assert cache.get(40.12, -73.98) == payload


def test_get_on_missing_key_returns_none(cache):
    assert cache.get(10.0, 20.0) is None


def test_key_rounding_merges_coordinates_within_0_01_degrees(cache):
    payload = {"temperature": 7.0, "code": "rain"}
    cache.set(40.121, -73.981, payload)
    # Within 0.01 degrees: rounds to the same 2-decimal cache key.
    assert cache.get(40.124, -73.984) == payload
    # Outside the bucket: a distinct cache entry.
    assert cache.get(40.13, -73.98) is None


def test_ttl_expired_row_returns_none(tmp_path, cache):
    db_path = str(tmp_path / "weather_cache.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO weather_cache(key, value, created_at) VALUES (?, ?, ?)",
            ("weather|40.12|-73.98", json.dumps({"temperature": 1.0}), "2020-01-01 00:00:00"),
        )
    assert cache.get(40.12, -73.98) is None


def test_sqlite_connect_error_returns_none_gracefully(cache, monkeypatch):
    def raise_sqlite_error(*args, **kwargs):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(sqlite3, "connect", raise_sqlite_error)
    assert cache.get(40.12, -73.98) is None
    assert cache.set(40.12, -73.98, {"temperature": 1.0}) is None


def test_corrupt_json_value_returns_none(tmp_path, cache):
    db_path = str(tmp_path / "weather_cache.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO weather_cache(key, value, created_at) VALUES (?, ?, ?)",
            ("weather|40.12|-73.98", "{not-valid-json", "now"),
        )
    assert cache.get(40.12, -73.98) is None
