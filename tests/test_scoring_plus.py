"""Micro-step 7/7 — spec 006-comfort-plus, task T2, AC-2/AC-3.

`prefer_lit` matrix: lit=yes vs lit=no vs missing-lit-tag, each with the
toggle on/off, asserting deterministic score flips (+2.0 only for lit=yes).

`avoid_traffic` matrix: primary/secondary/trunk vs residential/footway, each
with the toggle on/off, asserting quieter routing at modest detour cost
(busy -2.0 / quiet +2.0 with the toggle on; no-op when off).

Combined toggles: both on at once, asserting the equal-weight +2.0 lit bonus
and ±2.0 traffic delta compose additively (and cancel on a lit busy road).

Data gaps: `explain_comfort` reports the "lighting data unavailable here"
note exactly when the `lit` tag is missing.
"""

from typing import Any

import pytest

from app.scoring import explain_comfort, score_comfort

# Deterministic base: balanced score = (10-2)*3.5 + (30-0)*0.1 + (80-0)*0.05 = 35.0
BASE: dict[str, Any] = {"temp": 25, "humidity": 60, "wind_speed": 2}
BASE_SCORE = 35.0
LIT_BONUS = 2.0
TRAFFIC_DELTA = 2.0
BUSY = ("primary", "secondary", "trunk")
QUIET = ("residential", "footway")


def _features(lit: str | None) -> dict:
    features = dict(BASE)
    if lit is not None:
        features["lit"] = lit
    return features


def _road_features(highway: str) -> dict:
    features = dict(BASE)
    features["highway"] = highway
    return features


@pytest.mark.parametrize(
    ("lit", "prefer_lit", "expected"),
    [
        ("yes", False, BASE_SCORE),
        ("yes", True, BASE_SCORE + LIT_BONUS),
        ("no", False, BASE_SCORE),
        ("no", True, BASE_SCORE),
        (None, False, BASE_SCORE),
        (None, True, BASE_SCORE),
    ],
)
def test_prefer_lit_matrix(lit, prefer_lit, expected):
    assert score_comfort(_features(lit), "balanced", prefer_lit=prefer_lit) == pytest.approx(expected)


def test_prefer_lit_flips_only_when_lit_yes():
    # lit=yes: toggle flips the score by exactly +2.0
    off = score_comfort(_features("yes"), "balanced", prefer_lit=False)
    on = score_comfort(_features("yes"), "balanced", prefer_lit=True)
    assert on - off == pytest.approx(LIT_BONUS)

    # lit=no: toggle is a no-op (no bonus, no penalty)
    off = score_comfort(_features("no"), "balanced", prefer_lit=False)
    on = score_comfort(_features("no"), "balanced", prefer_lit=True)
    assert on == off

    # missing lit tag: toggle is a no-op
    off = score_comfort(_features(None), "balanced", prefer_lit=False)
    on = score_comfort(_features(None), "balanced", prefer_lit=True)
    assert on == off


def test_prefer_lit_explanation_factor():
    score, explanation = explain_comfort(_features("yes"), "balanced", prefer_lit=True)
    assert "lit bonus +2.0" in explanation["factors"]
    assert score == pytest.approx(BASE_SCORE + LIT_BONUS)

    _, explanation = explain_comfort(_features("no"), "balanced", prefer_lit=True)
    assert "lit bonus +2.0" not in explanation["factors"]

    _, explanation = explain_comfort(_features(None), "balanced", prefer_lit=True)
    assert "lit bonus +2.0" not in explanation["factors"]


@pytest.mark.parametrize(
    ("highway", "avoid_traffic", "expected"),
    [
        ("primary", False, BASE_SCORE),
        ("primary", True, BASE_SCORE - TRAFFIC_DELTA),
        ("secondary", False, BASE_SCORE),
        ("secondary", True, BASE_SCORE - TRAFFIC_DELTA),
        ("trunk", False, BASE_SCORE),
        ("trunk", True, BASE_SCORE - TRAFFIC_DELTA),
        ("residential", False, BASE_SCORE),
        ("residential", True, BASE_SCORE + TRAFFIC_DELTA),
        ("footway", False, BASE_SCORE),
        ("footway", True, BASE_SCORE + TRAFFIC_DELTA),
    ],
)
def test_avoid_traffic_matrix(highway, avoid_traffic, expected):
    assert score_comfort(
        _road_features(highway), "balanced", avoid_traffic=avoid_traffic
    ) == pytest.approx(expected)


def test_avoid_traffic_quieter_routing_at_modest_detour_cost():
    # Toggle on: quiet ways outrank busy roads by exactly 2 * TRAFFIC_DELTA
    for busy in BUSY:
        for quiet in QUIET:
            busy_on = score_comfort(_road_features(busy), "balanced", avoid_traffic=True)
            quiet_on = score_comfort(_road_features(quiet), "balanced", avoid_traffic=True)
            assert quiet_on - busy_on == pytest.approx(2 * TRAFFIC_DELTA)

    # Toggle off: highway tag is a no-op — every road scores identically
    for highway in BUSY + QUIET:
        off = score_comfort(_road_features(highway), "balanced", avoid_traffic=False)
        assert off == pytest.approx(BASE_SCORE)

    # Modest detour cost: the quiet-way advantage (4.0) exceeds the lit bonus (2.0),
    # so a short detour onto a quiet way is worth it, but the swing stays small.
    busy_on = score_comfort(_road_features("primary"), "balanced", avoid_traffic=True)
    quiet_on = score_comfort(_road_features("footway"), "balanced", avoid_traffic=True)
    assert quiet_on - busy_on == pytest.approx(2 * TRAFFIC_DELTA)
    assert quiet_on - busy_on <= 2 * LIT_BONUS + TRAFFIC_DELTA


def test_avoid_traffic_explanation_factor():
    _, explanation = explain_comfort(_road_features("primary"), "balanced", avoid_traffic=True)
    assert "busy-road penalty -2.0" in explanation["factors"]

    _, explanation = explain_comfort(_road_features("footway"), "balanced", avoid_traffic=True)
    assert "quiet-way bonus +2.0" in explanation["factors"]

    # Toggle off: no traffic factors reported
    _, explanation = explain_comfort(_road_features("primary"), "balanced", avoid_traffic=False)
    assert "busy-road penalty -2.0" not in explanation["factors"]
    assert "quiet-way bonus +2.0" not in explanation["factors"]


def test_combined_toggles_compose_additively():
    # lit=yes on a quiet way: the +2.0 lit bonus and +2.0 quiet-way bonus add
    assert score_comfort(
        _features("yes") | {"highway": "footway"},
        "balanced",
        prefer_lit=True,
        avoid_traffic=True,
    ) == pytest.approx(BASE_SCORE + LIT_BONUS + TRAFFIC_DELTA)

    assert score_comfort(
        _features("yes") | {"highway": "primary"},
        "balanced",
        prefer_lit=True,
        avoid_traffic=True,
    ) == pytest.approx(BASE_SCORE + LIT_BONUS - TRAFFIC_DELTA)

    assert score_comfort(
        _features("no") | {"highway": "primary"},
        "balanced",
        prefer_lit=True,
        avoid_traffic=True,
    ) == pytest.approx(BASE_SCORE - TRAFFIC_DELTA)

    # Both toggles off: combined features score the plain base
    assert score_comfort(
        _features("yes") | {"highway": "primary"},
        "balanced",
        prefer_lit=False,
        avoid_traffic=False,
    ) == pytest.approx(BASE_SCORE)


def test_equal_weight_contribution():
    # Equal weight: the +2.0 lit bonus exactly cancels the -2.0 busy-road penalty
    score, explanation = explain_comfort(
        _features("yes") | {"highway": "primary"},
        "balanced",
        prefer_lit=True,
        avoid_traffic=True,
    )
    assert score == pytest.approx(BASE_SCORE)
    assert "lit bonus +2.0" in explanation["factors"]
    assert "busy-road penalty -2.0" in explanation["factors"]

    # Same weight on the quiet side: lit bonus + quiet-way bonus = 2 * TRAFFIC_DELTA
    assert score_comfort(
        _features("yes") | {"highway": "footway"},
        "balanced",
        prefer_lit=True,
        avoid_traffic=True,
    ) == pytest.approx(BASE_SCORE + 2 * TRAFFIC_DELTA)


def test_data_gap_explanation_lighting_unavailable():
    # Missing lit tag: the gap note is reported
    _, explanation = explain_comfort(_features(None), "balanced", prefer_lit=True)
    assert explanation.get("gaps") == ["lighting data unavailable here"]

    # Missing lit tag even with both toggles on: gap note still reported
    _, explanation = explain_comfort(
        _features(None) | {"highway": "primary"},
        "balanced",
        prefer_lit=True,
        avoid_traffic=True,
    )
    assert "lighting data unavailable here" in explanation.get("gaps", [])

    # Lit tag present: no lighting gap note
    _, explanation = explain_comfort(_features("yes"), "balanced", prefer_lit=True)
    assert "lighting data unavailable here" not in explanation.get("gaps", [])
