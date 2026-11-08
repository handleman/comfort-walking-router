import requests

USER_AGENT = "comfort-walking-router/0.1 (learning project)"


def geocode_place(place: str) -> tuple[float, float]:
    url = "https://nominatim.openstreetmap.org/search"
    params: dict[str, str | int] = {"q": place, "format": "json", "limit": 1}
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"No results found for: {place}")
    result = data[0]
    return float(result['lat']), float(result['lon'])
