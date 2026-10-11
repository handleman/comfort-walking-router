from typing import Any


def score_comfort(features: dict[str, Any], preference: str = "balanced") -> float:
    """Score comfort based on features with preference weighting."""
    weights = {"comfort": 1.0, "performance": 1.0}
    if preference == "comfort":
        weights["comfort"] = 2.0
    elif preference == "performance":
        weights["performance"] = 2.0
    score = weights["comfort"] * features.get("comfort", 0) + weights["performance"] * features.get("performance", 0)
    return float(score)