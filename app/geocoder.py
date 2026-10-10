import requests


def geocode_place(place: str) -> tuple[float, float]:
    url = "https://nominatim.openstreetmap.org/search"
    params: dict[str, str | int] = {"q": place, "format": "json", "limit": 1}
    response = requests.get(url, params=params)
    data = response.json()
    if not data:
        raise ValueError(f"No results found for: {place}")
    result = data[0]
    return float(result['lat']), float(result['lon'])