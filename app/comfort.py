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
from dataclasses import dataclass
from typing import Any

from . import fixtures
from .providers import overpass

CORRIDOR_MARGIN_M = 60.0
QUIET_HIGHWAYS = frozenset(
    {"footway", "path", "pedestrian", "residential", "living_street", "steps"}
)

PROFILE_SEGMENT_M = 200.0
BANDS = ((0, 40, "poor"), (40, 70, "mixed"), (70, 100, "good"))


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in metres between two (lng, lat) pairs."""
    lng1, lat1 = (math.radians(v) for v in a)
    lng2, lat2 = (math.radians(v) for v in b)
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.asin(math.sqrt(math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2))
    return 2 * 6_371_000 * h


@dataclass(frozen=True)
class ProfileSegment:
    from_m: float
    to_m: float
    score: float
    factor: str
    label: str


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


def _segment_score(factors: dict[str, Any]) -> tuple[float, str, str]:
    """Score 0..100 for one segment plus its dominant factor and label."""
    shade = factors.get("shade_factor")
    quiet = factors.get("quiet_factor")
    lit = factors.get("lit_share")
    if shade is None and quiet is None and lit is None:
        return 50.0, "unknown", "no OSM data"
    # An individually missing factor contributes 0.0, not a penalty.
    # Plan weights: base 50, +20·shade, +15·quiet − 15·(1−quiet); lit is a
    # smaller term that can still dominate when shade/quiet are weak.
    terms: list[tuple[str, float, str]] = [
        ("shade", 20.0 * (shade or 0.0), "shaded" if (shade or 0.0) >= 0.5 else "exposed"),
        ("quiet", 30.0 * (quiet or 0.0) - 15.0, "quiet" if (quiet or 0.0) >= 0.5 else "busy"),
        ("lit", 10.0 * (lit or 0.0), "lit" if (lit or 0.0) >= 0.5 else "dark"),
    ]
    score = 50.0 + sum(weight for _, weight, _ in terms)
    name, weight, strength = max(terms, key=lambda t: t[1])
    if weight <= 0.0:
        # Nothing moved the score: name the ambient conditions instead.
        return (
            round(max(0.0, min(100.0, score)), 1),
            "traffic",
            "sun-exposed traffic corridor"[:40],
        )
    return (
        round(max(0.0, min(100.0, score)), 1),
        name,
        f"{strength} corridor"[:40],
    )


def profile(
    geometry: dict[str, Any],
    factors: dict[str, Any] | None,
    *,
    segment_m: float = PROFILE_SEGMENT_M,
) -> list[ProfileSegment] | None:
    """Walk the LineString, scoring contiguous segments of at most `segment_m`."""
    coords = geometry.get("coordinates") or []
    if not factors or not coords:
        return None
    segments: list[ProfileSegment] = []
    from_m = 0.0
    prev = (float(coords[0][0]), float(coords[0][1]))
    for point in coords[1:]:
        cur = (float(point[0]), float(point[1]))
        step = _haversine_m(prev, cur)
        while step > 0.0:
            span = min(segment_m, step)
            to_m = from_m + span
            score, factor, label = _segment_score(factors)
            segments.append(
                ProfileSegment(
                    from_m=round(from_m, 1),
                    to_m=round(to_m, 1),
                    score=score,
                    factor=factor,
                    label=label,
                )
            )
            from_m = to_m
            step -= span
        prev = cur
    if not segments:
        score, factor, label = _segment_score(factors)
        segments.append(
            ProfileSegment(from_m=0.0, to_m=0.0, score=score, factor=factor, label=label)
        )
    return segments


def weighted_score(segments: list[ProfileSegment]) -> float:
    """Distance-weighted mean of segment scores."""
    total = sum(s.to_m - s.from_m for s in segments)
    if total <= 0:
        return 0.0
    return sum(s.score * (s.to_m - s.from_m) for s in segments) / total
