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

import itertools
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "from_m": self.from_m,
            "to_m": self.to_m,
            "score": self.score,
            "factor": self.factor,
            "label": self.label,
        }


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
        "[out:json][timeout:40];\n(\n"
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


def _corridor_features(
    geometry: dict[str, Any], margin_m: float
) -> list[dict[str, Any]] | None:
    """The raw corridor features (fixtures in fixtures mode); None on failure."""
    try:
        box = corridor_bbox(geometry, margin_m)
    except ValueError:
        return None
    if fixtures.route_fixtures_enabled():
        return fixtures.recorded_corridor_features(geometry)
    return _overpass_features(overpass_query(box))


def _overpass_features(query: str) -> list[dict[str, Any]] | None:
    """Try the three Overpass endpoints in order.

    The public Overpass instance answers 502 "all query workers are busy" when it
    is at capacity (seen live 2026-11-15, which turned a real Munich route into a
    weather-only score with no comfort data). Retrying the mirrors is the
    difference between a data gap and a good route; anything worse is still a
    gap, never a failed route.
    """
    urls = (
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    )
    for attempt, url in enumerate(urls, start=1):
        try:
            features = overpass.fetch_overpass_features(url, query=query)
            if features:
                return features
        except Exception as exc:  # noqa: BLE001 - try the next endpoint
            print(f"overpass: attempt {attempt}/3 endpoint {url} failed, reason: {exc} — trying the next endpoint", flush=True)
            continue
        print(f"overpass: attempt {attempt}/3 endpoint {url} failed, reason: no features in response — trying the next endpoint", flush=True)
    print("overpass: all endpoints failed — falling back to a weather-only score", flush=True)
    # Data gap, never a 5xx: all endpoints failed, so return None and the
    # caller scores the route on weather alone.
    return None


def _as_elements(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """GeoJSON features -> the `{type, tags}` shape `count_features` reads."""
    out: list[dict[str, Any]] = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        kind = "way" if geometry.get("type") == "LineString" else "node"
        out.append({"type": kind, "tags": dict(feature.get("properties") or {})})
    return out


def corridor_data(
    geometry: dict[str, Any],
    *,
    margin_m: float = CORRIDOR_MARGIN_M,
) -> dict[str, Any] | None:
    """One corridor fetch → `{"factors": …, "feature_points": […]}` (028 AC-2)."""
    if fixtures.route_fixtures_enabled():
        # The fixture keeps its counted corridor (5 ways, 2 trees, 1 grass) so
        # the 001 tests stay exact, and positions a denser set of trees for the
        # profile — the two halves of the same story.
        counts = overpass.count_features(fixtures.recorded_corridor_elements())
        return {
            "factors": factors_from_counts(counts),
            "feature_points": feature_points(
                geometry, fixtures.recorded_corridor_features(geometry)
            ),
        }
    features = _corridor_features(geometry, margin_m)
    if features is None:
        return None
    try:
        counts = overpass.count_features(_as_elements(features))
    except Exception:  # noqa: BLE001 - malformed upstream payload is a data gap
        return None
    return {
        "factors": factors_from_counts(counts),
        "feature_points": feature_points(geometry, features),
    }


def corridor_factors(
    geometry: dict[str, Any],
    *,
    margin_m: float = CORRIDOR_MARGIN_M,
) -> dict[str, Any] | None:
    """Best-effort OSM factors for this route; None when Overpass is unusable."""
    data = corridor_data(geometry, margin_m=margin_m)
    return data["factors"] if data else None


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _segments_bounds(
    geometry_coords: list[list[float]], total_m: float | None, segment_m: float
) -> list[tuple[float, float, float, float]]:
    """(from_m, to_m, t0, t1) per segment, scaled to the route's own distance.

    The provider's `distance_m` is authoritative; the geometry is often a
    simplified two-point line (1234.5 m reported for a 1336 m straight line).
    Each segment therefore carries its fraction of the line, and the last one
    ends exactly at `total_m`.
    """
    lengths: list[float] = []
    for a, b in itertools.pairwise(geometry_coords):
        lengths.append(_haversine_m((float(a[0]), float(a[1])), (float(b[0]), float(b[1]))))
    raw_total = sum(lengths) or 1.0
    scale = (total_m / raw_total) if total_m else 1.0
    # Cut points in *scaled* metres, then map each to a fraction of the line.
    total = raw_total * scale
    cuts: list[tuple[float, float, float, float]] = []
    start = 0.0
    while start < total - 0.5:
        end = min(total, start + segment_m)
        cuts.append((start, end, start / total, end / total))
        start = end
    if not cuts:
        cuts.append((0.0, total, 0.0, 1.0))
    return cuts


def _local_factors(
    features: list[dict[str, Any]] | None,
    t0: float,
    t1: float,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    """Factors for the slice [t0, t1] of the route, from positioned features.

    `features` entries are `{"at": 0..1, "kind": "tree"|"green"|"quiet"|"busy"|
    "lit"}`. With no positioned features the corridor-level factors are used, so
    a profile is never invented from nothing.
    """
    merged = dict(fallback)
    if not features:
        return merged
    mid = (t0 + t1) / 2
    window = max(0.01, (t1 - t0))  # this segment, not its neighbours
    near = [f for f in features if abs(float(f.get("at", 0.0)) - mid) <= window]
    if not near:
        # No tree in this slice: open sky. Quiet/lit stay corridor-level, because
        # Overpass `out tags` returns ways without coordinates.
        merged["shade_factor"] = 0.0
        merged["source"] = "osm-corridor-segment"
        return merged
    kinds = [str(f.get("kind")) for f in near]
    trees = kinds.count("tree") + kinds.count("green")
    # Three trees (or green features) in one segment is a genuinely shaded
    # stretch; one is a street tree at the kerb.
    merged["shade_factor"] = round(min(1.0, trees / 3.0), 3)
    merged["source"] = "osm-corridor-segment"
    return merged


def _segment_score(
    factors: dict[str, Any], preference: str = "balanced"
) -> tuple[float, str, str]:
    """Score 0..100 for one slice plus its dominant factor and label.

    028 AC-1: the preference decides whether shade is a benefit or a cost, so a
    heat-avoider and a sun-seeker never get the same number for the same street.
    """
    shade = factors.get("shade_factor")
    quiet = factors.get("quiet_factor")
    lit = factors.get("lit_share")
    if shade is None and quiet is None and lit is None:
        return 50.0, "unknown", "no OSM data"
    shade_value = float(shade or 0.0)
    # +40·shade for heat/shade seekers, −40·shade for sun seekers, neutral else.
    shade_term = {
        "hot": 40.0 * (shade_value - 0.5),
        "cloudy": -40.0 * (shade_value - 0.5),
    }.get(preference, 0.0)
    quiet_term = 30.0 * float(quiet or 0.0) - 15.0
    lit_term = 10.0 * float(lit or 0.0)
    score = _clamp(50.0 + shade_term + quiet_term + lit_term)
    terms = [
        ("shade", shade_term, ("shaded" if shade_value >= 0.5 else "exposed")),
        ("quiet", quiet_term, ("quiet" if float(quiet or 0.0) >= 0.5 else "busy")),
        ("lit", lit_term, ("well lit" if float(lit or 0.0) >= 0.5 else "dark")),
    ]
    # The product question is "which part is shady": when the shade signal is
    # decisive for this preference it names the segment, even if quiet happens
    # to move the number a little more (028 AC-1).
    if shade_term != 0.0 and shade_value >= 0.5:
        factor = "shade" if shade_term > 0 else "sun"
        label = "shaded street" if factor == "shade" else "sunny side"
        return round(score, 1), factor, label[:40]
    if shade_term != 0.0 and shade_value <= 0.2 and shade_term < 0:
        return round(score, 1), "sun", "open and sunny"[:40]
    name, weight, strength = max(terms, key=lambda term: abs(term[1]))
    if weight == 0.0:
        return round(score, 1), "traffic", "sun-exposed traffic corridor"[:40]
    if name == "shade":
        factor = "shade" if shade_term > 0 else "sun"
        return round(score, 1), factor, f"{strength} ({factor})"[:40]
    if name == "quiet":
        # `quiet_factor` is a share of quiet ways: its term is negative on a
        # corridor made of busy roads, which the contract calls `traffic`.
        factor = "quiet" if quiet_term > 0 else "traffic"
        label = "quiet side street" if factor == "quiet" else "busy road"
        return round(score, 1), factor, label[:40]
    return round(score, 1), "lit", f"{strength} corridor"[:40]


def feature_points(
    geometry: dict[str, Any], features: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Project OSM features onto the route as 0..1 positions (028 AC-1).

    The projection is onto the route *segments*, not the vertices: a two-point
    route (most fixtures, and OSRM's simplified line) would otherwise collapse
    every tree onto one end. Deterministic and network-free; a feature with no
    point geometry is skipped because its tags already count at corridor level.
    """
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return []
    cumulative = [0.0]
    for a, b in itertools.pairwise(coords):
        cumulative.append(
            cumulative[-1] + _haversine_m((float(a[0]), float(a[1])), (float(b[0]), float(b[1])))
        )
    total = cumulative[-1] or 1.0
    points: list[dict[str, Any]] = []
    for feature in features:
        geometry_in = feature.get("geometry") or {}
        if geometry_in.get("type") != "Point":
            continue
        lng, lat = (float(v) for v in (geometry_in.get("coordinates") or [])[:2])
        best_at, best_distance = 0.0, float("inf")
        for index, (a, b) in enumerate(itertools.pairwise(coords)):
            ax, ay, bx, by = float(a[0]), float(a[1]), float(b[0]), float(b[1])
            dx, dy = bx - ax, by - ay
            length_sq = dx * dx + dy * dy
            if length_sq == 0:
                continue
            t = ((lng - ax) * dx + (lat - ay) * dy) / length_sq
            t = max(0.0, min(1.0, t))
            px, py = ax + t * dx, ay + t * dy
            distance = (lng - px) ** 2 + (lat - py) ** 2
            if distance < best_distance:
                from_m = cumulative[index] + t * (cumulative[index + 1] - cumulative[index])
                best_distance = distance
                best_at = from_m / total
        props = feature.get("properties") or {}
        kind = "tree" if props.get("natural") == "tree" else None
        kind = kind or ("green" if props.get("natural") in {"grass", "wood", "scrub"} else None)
        kind = kind or ("lit" if props.get("lit") == "yes" else None)
        if kind is None and props.get("highway"):
            kind = "quiet" if props["highway"] in QUIET_HIGHWAYS else "busy"
        if kind is None:
            continue
        points.append({"at": round(best_at, 4), "kind": kind})
    return points


def profile(
    geometry: dict[str, Any],
    factors: dict[str, Any] | None,
    *,
    feature_points_in: list[dict[str, Any]] | None = None,
    total_m: float | None = None,
    segment_m: float = PROFILE_SEGMENT_M,
    preference: str = "balanced",
) -> list[ProfileSegment] | None:
    """Contiguous segments of at most `segment_m`, scored per slice (028 AC-1)."""
    coords = geometry.get("coordinates") or []
    if not factors or not coords:
        return None
    segments: list[ProfileSegment] = []
    for from_m, to_m, t0, t1 in _segments_bounds(coords, total_m, segment_m):
        local = _local_factors(feature_points_in, t0, t1, factors)
        score, factor, label = _segment_score(local, preference)
        segments.append(
            ProfileSegment(
                from_m=round(from_m, 1),
                to_m=round(to_m, 1),
                score=score,
                factor=factor,
                label=label,
            )
        )
    return segments or None


def weighted_score(segments: list[ProfileSegment]) -> float:
    """Distance-weighted mean of segment scores."""
    total = sum(s.to_m - s.from_m for s in segments)
    if total <= 0:
        return 0.0
    return sum(s.score * (s.to_m - s.from_m) for s in segments) / total
