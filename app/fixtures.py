"""Offline test fixtures: route/geocode helpers backed by recorded data."""

import os


def route_fixtures_enabled() -> bool:
    """Return True when route fixtures are enabled via ROUTE_FIXTURES env var."""
    return os.environ.get("ROUTE_FIXTURES", "").strip().lower() in {"1", "true", "yes"}


# Recorded geocode results (latitude, longitude) captured from the live geocoder.
_RECORDED_GEOCODE: dict[str, tuple[float, float]] = {
    "central park": (40.7829, -73.9654),
    "times square": (40.7580, -73.9855),
}


def recorded_geocode(place: str) -> tuple[float, float]:
    """Return recorded coordinates for ``place`` or raise ValueError."""
    key = place.strip().lower()
    if key not in _RECORDED_GEOCODE:
        raise ValueError(f"No recorded geocode for place: {place!r}")
    return _RECORDED_GEOCODE[key]


# Recorded route result: GeoJSON FeatureCollection with distance/duration.
_RECORDED_ROUTE: dict = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"distance": 9500.0, "duration": 1200.0},
            "geometry": {
                "type": "LineString",
                "coordinates": [[-73.9855, 40.7580], [-73.9654, 40.7829]],
            },
        }
    ],
}


def recorded_route(
    start: tuple[float, float],
    end: tuple[float, float],
    preference: str | None = None,
) -> dict:
    """Return the recorded route FeatureCollection for ``start`` -> ``end``."""
    return _RECORDED_ROUTE


# Recorded Overpass results: list of GeoJSON feature dicts (POIs along the route).
_RECORDED_OVERPASS: list[dict] = [
    {
        "type": "Feature",
        "properties": {"name": "Central Park Zoo", "amenity": "zoo"},
        "geometry": {"type": "Point", "coordinates": [-73.9726, 40.7678]},
    },
    {
        "type": "Feature",
        "properties": {"name": "Times Square Cafe", "amenity": "cafe"},
        "geometry": {"type": "Point", "coordinates": [-73.9857, 40.7581]},
    },
]


def recorded_overpass_features() -> list[dict]:
    """Return the recorded Overpass feature dicts."""
    return _RECORDED_OVERPASS
