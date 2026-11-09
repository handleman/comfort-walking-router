"""Regression tests for the SQLite route cache (app.cache.Cache).

Covers spec 005-saved-routes task T9 acceptance criteria AC-4/AC-5:
round-trip fidelity, missing-key behavior, cache-key versioning stability,
insert-or-replace semantics, and preference-scoped cache keys.
"""

import sqlite3

import pytest

from app.cache import CACHE_VERSION, Cache


@pytest.fixture()
def cache(tmp_path):
    """Cache instance backed by a throwaway SQLite file in tmp_path."""
    return Cache(db_path=str(tmp_path / "cache.db"))


def test_set_get_round_trip_returns_identical_data(cache):
    payload = {"distance_km": 12.5, "geometry": [[52.5, 13.4], [52.6, 13.5]]}
    cache.set(("a", "b", "hot"), payload)
    assert cache.get(("a", "b", "hot")) == payload


def test_get_on_missing_key_returns_none(cache):
    assert cache.get(("missing", "start", None)) is None


def test_key_versioning_v2_prefix_is_stable(cache, tmp_path):
    start, end, preference = "a", "b", "hot"
    cache.set((start, end, preference), {"x": 1})

    with sqlite3.connect(str(tmp_path / "cache.db")) as conn:
        row = conn.execute("SELECT key FROM route_cache").fetchone()

    assert row is not None
    stored_key = row[0]
    assert stored_key.startswith(f"{CACHE_VERSION}|")
    assert stored_key == f"{CACHE_VERSION}|{start}|{end}|{preference}"

    # Reopening the same db keeps reading the v2-prefixed row.
    reopened = Cache(db_path=str(tmp_path / "cache.db"))
    assert reopened.get((start, end, preference)) == {"x": 1}


def test_insert_or_replace_overwrites_existing_value(cache):
    cache.set(("a", "b", None), {"version": 1})
    cache.set(("a", "b", None), {"version": 2})
    assert cache.get(("a", "b", None)) == {"version": 2}

    with sqlite3.connect(cache.db_path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM route_cache").fetchone()
        assert row is not None
        count = row[0]
    assert count == 1


def test_preference_is_part_of_cache_key(cache):
    cache.set(("a", "b", "hot"), {"preference": "hot"})
    cache.set(("a", "b", "cloudy"), {"preference": "cloudy"})

    assert cache.get(("a", "b", "hot")) == {"preference": "hot"}
    assert cache.get(("a", "b", "cloudy")) == {"preference": "cloudy"}

    with sqlite3.connect(cache.db_path) as conn:
        keys = {row[0] for row in conn.execute("SELECT key FROM route_cache")}
    assert len(keys) == 2
