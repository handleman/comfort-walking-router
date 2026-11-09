from typing import Any

# Tracks whether lighting data was present in the last scored feature set (for gap notes)
lit_data_available: bool = False


def score_comfort(
    features: dict[str, Any],
    preference: str = "balanced",
    *,
    prefer_lit: bool = False,
    avoid_traffic: bool = False,
) -> float:
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
    
    # prefer_lit: +2.0 bonus when the spot is lit; track data availability for gap notes
    global lit_data_available
    lit_data_available = "lit" in features
    if prefer_lit and features.get("lit") == "yes":
        score += 2.0

    # avoid_traffic: −2.0 penalty for busy roads, +2.0 bonus for quiet ways
    if avoid_traffic:
        highway = features.get("highway")
        if highway in ("primary", "secondary", "trunk"):
            score -= 2.0
        elif highway in ("residential", "footway", "path"):
            score += 2.0

    return max(0.0, float(score))


def explain_comfort(
    features: dict[str, Any],
    preference: str = "balanced",
    *,
    prefer_lit: bool = False,
    avoid_traffic: bool = False,
) -> tuple[float, dict[str, Any]]:
    """Return (score, explanation) with the list of active factors and gap notes."""
    score = score_comfort(
        features, preference, prefer_lit=prefer_lit, avoid_traffic=avoid_traffic
    )

    factors: list[str] = []
    if not features:
        factors.append("no features")
    else:
        factors.append(f"preference={preference}")
        if prefer_lit and features.get("lit") == "yes":
            factors.append("lit bonus +2.0")
        if avoid_traffic:
            highway = features.get("highway")
            if highway in ("primary", "secondary", "trunk"):
                factors.append("busy-road penalty -2.0")
            elif highway in ("residential", "footway", "path"):
                factors.append("quiet-way bonus +2.0")

    explanation: dict[str, Any] = {"factors": factors}
    if "lit" not in features:
        explanation["gaps"] = ["lighting data unavailable here"]

    return score, explanation