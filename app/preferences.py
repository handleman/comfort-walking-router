"""User weather preferences (thresholds)."""

TEMP_HOT_THRESHOLD = 25.0
CLOUD_OVERCAST_THRESHOLD = 70.0


def auto_preference(temperature, cloud_cover, caller_preference):
    """Return an automatic preference based on weather, else the caller's."""
    if temperature is None or cloud_cover is None:
        return caller_preference
    if temperature >= TEMP_HOT_THRESHOLD and cloud_cover < CLOUD_OVERCAST_THRESHOLD:
        return "hot"
    if cloud_cover >= CLOUD_OVERCAST_THRESHOLD:
        return "cloudy"
    return caller_preference
