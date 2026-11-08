"""User weather preferences (thresholds)."""

TEMP_HOT_THRESHOLD = 25.0
CLOUD_OVERCAST_THRESHOLD = 70.0


def auto_preference(temperature, cloud_cover=None, caller_preference=None):
    """Return an automatic preference based on weather, else the caller's.

    Accepts either ``auto_preference(weather, caller_preference)`` (used by
    the route endpoint) or the legacy
    ``auto_preference(temperature, cloud_cover, caller_preference)``.
    """
    if caller_preference is None:
        weather = temperature if isinstance(temperature, dict) else None
        caller_preference = cloud_cover
    else:
        weather = {"temperature": temperature, "cloud_cover": cloud_cover}
    if not isinstance(weather, dict):
        return caller_preference
    temperature = weather.get("temperature")
    cloud_cover = weather.get("cloud_cover")
    if temperature is None or cloud_cover is None:
        return caller_preference
    if temperature >= TEMP_HOT_THRESHOLD and cloud_cover < CLOUD_OVERCAST_THRESHOLD:
        return "hot"
    if cloud_cover >= CLOUD_OVERCAST_THRESHOLD:
        return "cloudy"
    return caller_preference
