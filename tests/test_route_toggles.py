"""AC-1 (spec 006-comfort-plus, T3): route comfort toggles.

API-level checks that the ``prefer_lit`` and ``avoid_traffic`` toggles
flip comfort scoring on fixture pairs (lit vs dark, quiet vs busy).
"""

from typing import Any

import pytest

from app.scoring import explain_comfort, score_comfort

BASE: dict[str, Any] = {"temp": 20, "humidity": 55, "wind_speed": 3}

# Fixture pair 1: identical conditions, lit vs unlit way
LIT: dict[str, Any] = {**BASE, "lit": "yes"}
DARK: dict[str, Any] = {**BASE, "lit": "no"}

# Fixture pair 2: identical conditions, quiet residential vs busy primary
QUIET: dict[str, Any] = {**BASE, "highway": "residential"}
BUSY: dict[str, Any] = {**BASE, "highway": "primary"}


@pytest.mark.parametrize("features", [LIT, DARK], ids=["lit", "dark"])
def test_prefer_lit_flips_score_on_fixture_pair(features: dict[str, Any]) -> None:
    without_toggle = score_comfort(features, "balanced")
    with_toggle = score_comfort(features, "balanced", prefer_lit=True)

    if features["lit"] == "yes":
        assert with_toggle == pytest.approx(without_toggle + 2.0)
    else:
        # The toggle must never invent lighting that is not in the data.
        assert with_toggle == pytest.approx(without_toggle)


def test_prefer_lit_flips_ranking_between_pair() -> None:
    # Without the toggle the pair scores identically.
    assert score_comfort(LIT, "balanced") == pytest.approx(
        score_comfort(DARK, "balanced")
    )
    # With the toggle the lit way must outrank the dark one.
    assert score_comfort(LIT, "balanced", prefer_lit=True) > score_comfort(
        DARK, "balanced", prefer_lit=True
    )


@pytest.mark.parametrize("features", [QUIET, BUSY], ids=["quiet", "busy"])
def test_avoid_traffic_flips_score_on_fixture_pair(features: dict[str, Any]) -> None:
    without_toggle = score_comfort(features, "balanced")
    with_toggle = score_comfort(features, "balanced", avoid_traffic=True)

    if features["highway"] == "primary":
        assert with_toggle == pytest.approx(without_toggle - 2.0)
    else:
        assert with_toggle == pytest.approx(without_toggle + 2.0)


def test_avoid_traffic_flips_ranking_between_pair() -> None:
    # Without the toggle the pair scores identically.
    assert score_comfort(QUIET, "balanced") == pytest.approx(
        score_comfort(BUSY, "balanced")
    )
    # With the toggle the quiet way must outrank the busy one.
    assert score_comfort(QUIET, "balanced", avoid_traffic=True) > score_comfort(
        BUSY, "balanced", avoid_traffic=True
    )


def test_both_toggles_stack_on_lit_quiet_way() -> None:
    way = {**LIT, "highway": "residential"}

    base = score_comfort(way, "balanced")
    toggled = score_comfort(way, "balanced", prefer_lit=True, avoid_traffic=True)

    assert toggled == pytest.approx(base + 4.0)


def test_explain_comfort_applies_same_toggles() -> None:
    score, _explanation = explain_comfort(
        LIT, "balanced", prefer_lit=True, avoid_traffic=True
    )

    assert score == pytest.approx(
        score_comfort(LIT, "balanced", prefer_lit=True, avoid_traffic=True)
    )
