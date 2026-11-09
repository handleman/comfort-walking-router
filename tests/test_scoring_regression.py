"""Regression tests for comfort scoring and cache versioning (spec 006-comfort-plus, task T5).

Covers AC-4 (scoring regression baselines) and AC-5 (cache version bump invalidation).
"""

import json
from typing import cast

import pytest

from app.cache import CACHE_VERSION, Cache
from app.scoring import score_comfort

SHADED: dict = {
    "temp": 18,
    "humidity": 70,
    "wind_speed": 2,
    "lit": "yes",
    "highway": "footway",
}

SUNNY: dict = {
    "temp": 28,
    "humidity": 40,
    "wind_speed": 4,
    "lit": "no",
    "highway": "residential",
}

QUIET_SHADED: dict = {
    "temp": 20,
    "humidity": 65,
    "wind_speed": 1,
    "lit": "yes",
    "highway": "path",
}


# --- Micro-step 2/8: preference scorer regression (AC-4) -------------------

@pytest.mark.parametrize(
    "preference,features,expected",
    [
        ("hot", SHADED, SUNNY),        # hot prefers shade
        ("cloudy", SUNNY, SHADED),     # cloudy prefers sun
        ("balanced", QUIET_SHADED, SHADED),  # balanced prefers quiet
    ],
    ids=["hot-prefers-shade", "cloudy-prefers-sun", "balanced-prefers-quiet"],
)
def test_preference_prefers_matching_features(
    preference: str, features: dict, expected: dict
) -> None:
    """Each preference scores its matching feature set above the mismatched one."""
    assert score_comfort(features, preference) > score_comfort(expected, preference)


@pytest.mark.parametrize(
    "preference,features",
    [
        ("hot", SHADED),
        ("cloudy", SUNNY),
        ("balanced", QUIET_SHADED),
    ],
    ids=["hot-max", "cloudy-max", "balanced-max"],
)
def test_matching_preference_gives_max_score(preference: str, features: dict) -> None:
    """For a fixed preference, the matching feature set scores at least as high as any other."""
    matching = score_comfort(features, preference)
    for other_features in (SHADED, SUNNY, QUIET_SHADED):
        assert matching >= score_comfort(other_features, preference)


@pytest.mark.parametrize("preference", ["hot", "cloudy", "balanced"])
def test_empty_features_return_zero(preference: str) -> None:
    """Empty feature dicts score exactly zero for every preference."""
    assert score_comfort({}, preference) == 0.0


@pytest.mark.parametrize("preference", ["bogus", "", None, "HOT"])
def test_unknown_preference_falls_back_to_balanced(preference: str | None) -> None:
    """Unknown preferences fall back to balanced scoring (no error)."""
    # score_comfort normalizes any unrecognized preference (including None) to
    # "balanced"; cast documents that contract for the type checker.
    pref = cast(str, preference)
    assert score_comfort(QUIET_SHADED, pref) == score_comfort(QUIET_SHADED, "balanced")


@pytest.mark.parametrize("preference", ["hot", "cloudy", "balanced"])
def test_missing_keys_no_keyerror(preference: str) -> None:
    """Partially specified features use defaults instead of raising KeyError."""
    partial: dict = {"temp": 22}
    try:
        score = score_comfort(partial, preference)
    except KeyError as exc:  # pragma: no cover - failure path
        pytest.fail(f"KeyError raised for missing keys: {exc}")
    assert isinstance(score, float)


# --- Micro-step 3/8: cache regression (AC-5) --------------------------------


@pytest.fixture()
def cache(tmp_path) -> Cache:
    """Cache instance backed by a per-test SQLite file under tmp_path."""
    return Cache(str(tmp_path / "cache.db"))


def test_cache_set_get_round_trip(cache):
    """A value stored via set() is returned unchanged by get()."""
    payload = {"distance": 1234, "duration": 600, "geometry": "encoded"}
    cache.set(("a", "b", "hot"), payload)
    assert cache.get(("a", "b", "hot")) == payload


def test_cache_missing_key_returns_none(cache):
    """get() on a never-set key returns None instead of raising."""
    assert cache.get(("missing", "start", None)) is None


def test_cache_key_uses_v2_prefix(cache, tmp_path):
    """Cache keys are prefixed with the stable v2 version string."""
    cache.set(("s", "e", "hot"), {"x": 1})
    import sqlite3

    with sqlite3.connect(str(tmp_path / "cache.db")) as conn:
        (stored_key,) = conn.execute("SELECT key FROM route_cache").fetchone()
    assert stored_key.startswith(f"{CACHE_VERSION}|")


def test_cache_insert_or_replace_overwrites(cache):
    """Setting the same key twice replaces the stored value."""
    cache.set(("a", "b", None), {"v": 1})
    cache.set(("a", "b", None), {"v": 2})
    assert cache.get(("a", "b", None)) == {"v": 2}


def test_cache_preference_is_part_of_key(cache):
    """Different preferences for the same route do not collide in the cache."""
    cache.set(("a", "b", "hot"), {"pref": "hot"})
    cache.set(("a", "b", "cloudy"), {"pref": "cloudy"})
    assert cache.get(("a", "b", "hot")) == {"pref": "hot"}
    assert cache.get(("a", "b", "cloudy")) == {"pref": "cloudy"}


# --- Micro-step 4/8: contract regression (AC-4, AC-5) -----------------------


@pytest.fixture(scope="module")
def route_contract() -> dict:
    """The route JSON Schema contract, loaded once for this module."""
    with open("contracts/route.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_route_request_defines_prefer_lit(route_contract):
    """RouteRequest.prefer_lit is a boolean defaulting to false."""
    prop = route_contract["$defs"]["RouteRequest"]["properties"]["prefer_lit"]
    assert prop["type"] == "boolean"
    assert prop["default"] is False


def test_route_request_defines_avoid_traffic(route_contract: dict) -> None:
    """RouteRequest.avoid_traffic is a boolean defaulting to false."""
    prop = route_contract["$defs"]["RouteRequest"]["properties"]["avoid_traffic"]
    assert prop["type"] == "boolean"
    assert prop["default"] is False
