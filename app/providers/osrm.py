import requests

from .base import RouteProvider


class OSRMProvider(RouteProvider):
    def __init__(self):
        self.base_url = "https://router.project-osrm.org"

    def route(self, start: tuple[float, float], end: tuple[float, float], preference: str | None = None) -> dict:
        """Calculate route using OSRM demo API and return GeoJSON with distance/time."""
        (slat, slon), (elat, elon) = start, end
        url = f"{self.base_url}/route/v1/driving/{slon},{slat};{elon},{elat}"
        params = {"overview": "full", "geometries": "geojson"}
        if preference:
            params["annotations"] = preference
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": data["routes"][0]["geometry"]},
                "properties": {
                    "distance": data["routes"][0]["distance"],
                    "duration": data["routes"][0]["duration"]
                }
            }]
        }