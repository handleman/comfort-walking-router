"""Offline test fixtures: route/geocode helpers backed by recorded data."""

import os


def route_fixtures_enabled() -> bool:
    """Return True when route fixtures are enabled via ROUTE_FIXTURES env var."""
    return os.environ.get("ROUTE_FIXTURES", "").strip().lower() in {"1", "true", "yes"}


# Recorded geocode results (latitude, longitude) captured from the live geocoder.
_RECORDED_GEOCODE: dict[str, tuple[float, float]] = {
    "central park": (40.7829, -73.9654),
    "times square": (40.7580, -73.9855),
    # The UI placeholders are Munich and the 010/014 e2e specs use them.
    "marienplatz, munich": (48.1374, 11.5755),
    "englischer garten": (48.1642, 11.6056),
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


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    import math

    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def recorded_route(
    start: tuple[float, float],
    end: tuple[float, float],
    preference: str | None = None,
) -> dict:
    """Return a FeatureCollection for ``start`` -> ``end`` built from both points.

    The geometry used to be one hardcoded NYC line, so a Munich scenario drew a
    route at the wrong place and walk-mode placed its marker off the map.
    """
    distance = _haversine_m(start, end)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"distance": round(distance, 1), "duration": round(distance / 1.4, 1)},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[start[1], start[0]], [end[1], end[0]]],
                },
            }
        ],
    }


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
