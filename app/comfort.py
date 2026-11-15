"""Corridor comfort factors from OSM (001 AC-2).

`providers/overpass.py` can fetch and count OSM features and `features.py` can
map one element's tags, but until now nothing joined them to a route: the score
was weather-only and the explanation named shade/quiet factors it never had
(the 2026-11-15 review called this out — `fetch_overpass_features` had no
caller).

This module is the join. It bounds a corridor around the route geometry, asks
Overpass for the ways (`highway`, `lit`) and trees inside it, and turns the
counts into normalized factors the scorer and the explanation can use:

    shade_factor  trees + grass per mapped way, capped at 1.0
    quiet_factor  share of ways that are footway/path/pedestrian/residential
    lit_share     share of ways tagged `lit=yes`

Every factor is `None` when the corridor has no mapped ways, and the whole
result is `None` when Overpass fails — a route is never rejected because a
best-effort comfort lookup timed out. `ROUTE_FIXTURES=1` uses the recorded
corridor so e2e and tests stay hermetic and deterministic.

No score lives here: `scoring.py` owns the weights.
"""

from __future__ import annotations

import math
from typing import Any

from . import fixtures
from .providers import overpass

CORRIDOR_MARGIN_M = 60.0
QUIET_HIGHWAYS = frozenset(
    {"footway", "path", "pedestrian", "residential", "living_street", "steps"}
)


def corridor_bbox(
    geometry: dict[str, Any], margin_m: float = CORRIDOR_MARGIN_M
) -> tuple[float, float, float, float]:
    """(south, west, north, east) around a route's LineString, in degrees."""
    coords = geometry.get("coordinates") or []
    if not coords:
        raise ValueError("route geometry has no coordinates")
    lats = [float(point[1]) for point in coords]
    lngs = [float(point[0]) for point in coords]
    mid_lat = (min(lats) + max(lats)) / 2
    dlat = margin_m / 111_320.0
    # Longitude shrinks with latitude; clamp the cosine so a polar route does
    # not produce an absurd box.
    dlng = margin_m / (111_320.0 * max(0.2, math.cos(math.radians(mid_lat))))
    return (
        round(min(lats) - dlat, 6),
        round(min(lngs) - dlng, 6),
        round(max(lats) + dlat, 6),
        round(max(lngs) + dlng, 6),
    )


def overpass_query(box: tuple[float, float, float, float]) -> str:
    """Ways with a road/path class, plus trees, inside the corridor."""
    south, west, north, east = box
    return (
        "[out:json][timeout:10];\n(\n"
        f"  way[highway]({south},{west},{north},{east});\n"
        f"  node[natural=tree]({south},{west},{north},{east});\n"
        f"  way[natural=wood]({south},{west},{north},{east});\n"
        ");\nout tags;"
    )


def factors_from_counts(counts: dict[str, Any]) -> dict[str, Any]:
    """Normalize Overpass counts into 0..1 factors (None when unmeasured)."""
    breakdown: dict[str, int] = dict(counts.get("highway_breakdown") or {})
    ways = sum(breakdown.values())
    trees = int(counts.get("trees") or 0)
    grass = int(counts.get("grass") or 0)
    lit_ways = int(counts.get("lit_ways") or 0)
    quiet_ways = sum(count for name, count in breakdown.items() if name in QUIET_HIGHWAYS)
    result: dict[str, Any] = {
        "osm_ways": ways,
        "osm_trees": trees,
        "osm_green": trees + grass,
        "highway_breakdown": breakdown,
    }
    if ways:
        result["shade_factor"] = round(min(1.0, (trees + grass) / ways), 3)
        result["quiet_factor"] = round(quiet_ways / ways, 3)
        result["lit_share"] = round(lit_ways / ways, 3)
        # `highway` and `lit` are single-element tags in the legacy scorer; the
        # corridor is a distribution, so expose its dominant class too.
        result["highway"] = max(breakdown, key=lambda name: breakdown[name])
        if lit_ways:
            result["lit"] = "yes"
    else:
        result["shade_factor"] = None
        result["quiet_factor"] = None
        result["lit_share"] = None
    result["source"] = "osm-corridor"
    return result


def _as_elements(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """GeoJSON features -> the `{type, tags}` shape `count_features` reads."""
    out: list[dict[str, Any]] = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        kind = "way" if geometry.get("type") == "LineString" else "node"
        out.append({"type": kind, "tags": dict(feature.get("properties") or {})})
    return out


def corridor_factors(
    geometry: dict[str, Any],
    *,
    margin_m: float = CORRIDOR_MARGIN_M,
) -> dict[str, Any] | None:
    """Best-effort OSM factors for this route; None when Overpass is unusable."""
    try:
        box = corridor_bbox(geometry, margin_m)
    except ValueError:
        return None
    if fixtures.route_fixtures_enabled():
        elements = fixtures.recorded_corridor_elements()
    else:
        try:
            features = overpass.fetch_overpass_features(
                overpass.OVERPASS_URL, query=overpass_query(box)
            )
        except Exception:  # noqa: BLE001 - best effort: a score must still return
            return None
        elements = _as_elements(features)
    try:
        counts = overpass.count_features(elements)
    except Exception:  # noqa: BLE001 - malformed upstream payload is a data gap
        return None
    return factors_from_counts(counts)
