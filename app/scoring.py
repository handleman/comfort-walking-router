from typing import Any


def score_comfort(features: dict[str, Any], preference: str = "balanced") -> float:
    """Score comfort based on features with preference weighting.
    
    Preferences:
    - "hot": prefers shade (lower temp, higher humidity, lower wind)
    - "cloudy": prefers sun (higher temp, lower humidity)
    - "balanced": prefers quiet (lower wind, moderate temp/humidity)
    """
    if not features:
        return 0.0
    
    # Normalize preference
    if preference not in ("hot", "cloudy", "balanced"):
        preference = "balanced"
    
    temp = features.get("temp", 25)
    humidity = features.get("humidity", 50)
    wind_speed = features.get("wind_speed", 5)
    
    if preference == "hot":
        # Prefers shade: heavily weight cooler temp, moderately weight humidity, lightly weight low wind
        score = (35 - temp) * 1.5 + humidity * 0.3 + (10 - wind_speed) * 0.2
    elif preference == "cloudy":
        # Prefers sun: heavily weight warmer temp, moderately weight low humidity, lightly weight low wind
        score = (temp - 15) * 1.5 + (80 - humidity) * 0.3 + (10 - wind_speed) * 0.2
    else:  # balanced
        # Prefers quiet: heavily weight low wind, lightly weight moderate temp/humidity
        score = (10 - wind_speed) * 3.5 + (30 - abs(temp - 25)) * 0.1 + (80 - abs(humidity - 60)) * 0.05
    
    return max(0.0, float(score))