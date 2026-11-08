import pytest

from app.scoring import score_comfort

SHADED = {"temp": 25, "humidity": 60, "wind_speed": 3}
SUNNY = {"temp": 40, "humidity": 30, "wind_speed": 5}
QUIET_SHADED = {"temp": 28, "humidity": 70, "wind_speed": 1}


@pytest.mark.parametrize("feature", [SHADED, QUIET_SHADED])
def test_hot_prefers_shade(feature):
    assert score_comfort(feature, "hot") > score_comfort(SUNNY, "hot")


def test_cloudy_prefers_sun():
    assert score_comfort(SUNNY, "cloudy") > score_comfort(SHADED, "cloudy")


def test_balanced_prefers_quiet():
    assert score_comfort(QUIET_SHADED, "balanced") > score_comfort(SHADED, "balanced")


@pytest.mark.parametrize("feature,preference", [
    (SHADED, "hot"),
    (SUNNY, "cloudy"),
    (QUIET_SHADED, "balanced"),
])
def test_matching_preference_gives_max_score(feature, preference):
    # Assert that the matching preference gives the maximum score across all preferences
    max_score = -float('inf')
    for pref in ["hot", "cloudy", "balanced"]:
        max_score = max(max_score, score_comfort(feature, pref))
    assert score_comfort(feature, preference) == max_score


@pytest.mark.parametrize("feature", [SHADED, SUNNY, QUIET_SHADED])
def test_empty_features_returns_zero(feature):
    # Test that empty features return 0.0
    assert score_comfort({}, "hot") == 0.0
    assert score_comfort({}, "cloudy") == 0.0
    assert score_comfort({}, "balanced") == 0.0


def test_unknown_preference_falls_back_to_balanced():
    # Test that unknown preference falls back to balanced scoring
    assert score_comfort(SHADED, "unknown_pref") == score_comfort(SHADED, "balanced")
    assert score_comfort(SUNNY, "unknown_pref") == score_comfort(SUNNY, "balanced")


def test_missing_keys_no_keyerror():
    # Test that missing keys do not raise KeyError
    partial_feature = {"temp": 25}
    assert score_comfort(partial_feature, "hot") is not None
    assert score_comfort(partial_feature, "cloudy") is not None
    assert score_comfort(partial_feature, "balanced") is not None