
async def fetch_overpass_features(bbox: tuple[str, float, float, float, float]) -> dict:
    """
    Queries Overpass for trees, grass, and quiet highways.
    
    Args:
        bbox: A tuple of (min_lon, min_lat, max_lon, max_lat, zoom_level)
    
    Returns:
        A dictionary containing the features found.
    """
    return {}
