"""Open-Meteo weather provider client.

Fetches current weather conditions from the Open-Meteo public API.
"""

import requests

USER_AGENT = "comfort-walking-router/0.1 (learning project)"


class OpenMeteoProvider:
    """Client for the Open-Meteo forecast API."""

    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1/forecast"

    def fetch_current(self, lat: float, lon: float) -> dict[str, float] | None:
        """Fetch current temperature (°C) and cloud cover (%) for a location."""
        try:
            params: dict[str, str | float] = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,cloud_cover",
            }
            response = requests.get(
                self.base_url,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            return None
        return {
            "temperature": data["current"]["temperature_2m"],
            "cloud_cover": data["current"]["cloud_cover"],
        }
