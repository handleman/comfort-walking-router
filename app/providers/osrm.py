import requests

from .base import RouteProvider

USER_AGENT = "comfort-walking-router/0.1 (learning project)"


class OSRMProvider(RouteProvider):
    def __init__(self) -> None:
        self.base_url = "https://router.project-osrm.org"

    def route(self, start: tuple[float, float], end: tuple[float, float], preference: str | None = None) -> dict:
        """Calculate route using OSRM demo API and return GeoJSON with distance/time."""
        (slat, slon), (elat, elon) = start, end
        url = f"{self.base_url}/route/v1/driving/{slon},{slat};{elon},{elat}"
        # `preference` is applied by the comfort scorer, not by OSRM.
        params = {"overview": "full", "geometries": "geojson"}
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                # With geometries=geojson OSRM already returns a GeoJSON geometry.
                "geometry": data["routes"][0]["geometry"],
                "properties": {
                    "distance": data["routes"][0]["distance"],
                    "duration": data["routes"][0]["duration"]
                }
            }]
        }
