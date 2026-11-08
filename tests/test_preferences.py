"""Tests for auto weather preference (hot-sunny matrix)."""

import pytest

from app.preferences import auto_preference


@pytest.mark.parametrize(
    ("temperature", "cloud_cover", "expected"),
    [
        (25.0, 0, "hot"),
        (25.0, 69.9, "hot"),
        (30.0, 50, "hot"),
        (40.0, 0, "hot"),
    ],
)
def test_hot_sunny_matrix(temperature, cloud_cover, expected):
    """temp >= 25C and cloud < 70% -> 'hot'."""
    assert auto_preference(temperature, cloud_cover, "cool") == expected


@pytest.mark.parametrize(
    ("temperature", "cloud_cover", "expected"),
    [
        (25.0, 70, "cloudy"),
        (30.0, 70, "cloudy"),
        (40.0, 70, "cloudy"),
        (40.0, 100, "cloudy"),
        (10.0, 85, "cloudy"),
    ],
)
def test_overcast_matrix(temperature, cloud_cover, expected):
    """cloud >= 70% -> 'cloudy' (even when hot)."""
    assert auto_preference(temperature, cloud_cover, "cool") == expected


@pytest.mark.parametrize(
    ("temperature", "cloud_cover", "expected"),
    [
        (24.9, 0, "cool"),
        (24.9, 69.9, "cool"),
        (10.0, 50, "cool"),
        (0.0, 0, "cool"),
    ],
)
def test_cool_fallback_matrix(temperature, cloud_cover, expected):
    """temp < 25C and cloud < 70% -> caller preference."""
    assert auto_preference(temperature, cloud_cover, "cool") == expected


@pytest.mark.parametrize(
    ("temperature", "cloud_cover"),
    [
        (25.0, 70.0),
        (25.0, 70),
    ],
)
def test_exact_boundary_is_cloudy(temperature, cloud_cover):
    """temp exactly 25 with cloud exactly 70 -> 'cloudy'."""
    assert auto_preference(temperature, cloud_cover, "cool") == "cloudy"


@pytest.mark.parametrize(
    ("temperature", "cloud_cover"),
    [
        (None, 50),
        (30.0, None),
        (None, None),
    ],
)
def test_missing_data_falls_back_to_caller(temperature, cloud_cover):
    """None temperature or cloud_cover -> caller preference."""
    assert auto_preference(temperature, cloud_cover, "cool") == "cool"
