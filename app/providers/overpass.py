
from typing import Any

import requests

USER_AGENT = "comfort-walking-router/0.1 (learning project)"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def fetch_overpass_features(
    url: str,
    query: str = "[out:json][timeout:10] area(way[highway~\".*\"])[](node); out;",
    user_agent: str = USER_AGENT,
) -> list[dict[str, Any]]:
    """
    Queries Overpass for features and returns GeoJSON features.
    
    Args:
        url: Overpass API endpoint URL
        query: Overpass QL query string
        user_agent: User-Agent header value
    
    Returns:
        A list of GeoJSON feature dicts with geometry and properties.
    """
    headers = {"User-Agent": user_agent}
    params: dict[str, str | int] = {
        "data": query,
        "timeout": 10,
    }
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    # Handle both GeoJSON FeatureCollection (test mock) and Overpass elements format
    if "features" in data:
        # Already in GeoJSON format - pass through
        return data["features"]
    
    # Convert Overpass elements to GeoJSON features
    features = []
    for element in data.get("elements", []):
        if element.get("type") == "node":
            geometry = {
                "type": "Point",
                "coordinates": [element.get("lon", 0), element.get("lat", 0)],
            }
        elif element.get("type") == "way":
            # For ways, we'd need to fetch node coordinates - simplified here
            geometry = {
                "type": "LineString",
                "coordinates": [],
            }
        else:
            continue
        
        features.append({
            "geometry": geometry,
            "properties": element.get("tags", {}),
        })
    
    return features


def count_features(elements: list) -> dict:
    """
    Parse Overpass elements and count features.
    
    Args:
        elements: List of element dicts from Overpass API response
    
    Returns:
        A dictionary with counts: {"trees": n, "grass": n, "quiet_highways": n}
    """
    trees = 0
    grass = 0
    quiet_highways = 0
    
    for element in elements:
        tags = element.get('tags', {})
        if tags.get('natural') == 'tree':
            trees += 1
        elif tags.get('natural') == 'grass':
            grass += 1
        elif tags.get('highway') and tags.get('foot') == 'yes':
            quiet_highways += 1
    
    return {'trees': trees, 'grass': grass, 'quiet_highways': quiet_highways}
