import requests

from .base import RouteProvider

USER_AGENT = "comfort-walking-router/0.1 (learning project)"
BASE_URL = "https://api.mapbox.com/directions/v5"
PROFILE = "mapbox/walking"
TIMEOUT_SECONDS = 10


class MapboxProvider(RouteProvider):
    """Walking routes via the Mapbox Directions API.

    Returns a GeoJSON FeatureCollection with one LineString feature per
    route, each carrying ``distance`` (meters) and ``duration`` (seconds).
    """

    def __init__(self, access_token: str, alternatives: int = 1) -> None:
        self.access_token = access_token
        # Mapbox allows at most 2 alternatives; keep the value in 1..2.
        self.alternatives = min(2, max(1, int(alternatives)))
        self.base_url = BASE_URL

    def route(self, start: tuple[float, float], end: tuple[float, float], preference: str | None = None) -> dict:
        """Calculate walking routes and return GeoJSON with distance/time."""
        (slat, slon), (elat, elon) = start, end
        coordinates = f"{slon},{slat};{elon},{elat}"
        url = f"{self.base_url}/{PROFILE}/{coordinates}"
        params = {
            "alternatives": str(self.alternatives),
            "overview": "full",
            "geometries": "geojson",
            "access_token": self.access_token,
        }
        headers = {"User-Agent": USER_AGENT}
        # 10s timeout with a single retry on transport errors.
        try:
            response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
        except requests.RequestException:
            response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        features = []
        for route in data.get("routes", []):
            features.append({
                "type": "Feature",
                "geometry": route["geometry"],
                "properties": {
                    "distance": route["distance"],
                    "duration": route["duration"],
                },
            })
        return {"type": "FeatureCollection", "features": features}
