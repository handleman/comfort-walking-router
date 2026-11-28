"""Geocoding suggestions from Mapbox (Geocoding v6) or Photon.

The single source of truth for the suggestion shape (spec 014, AC-8). Every
provider is normalized into `Suggestion` here, so the HTTP layer, the JSON
contract and the frontend all see one shape and no provider payload leaks
past this module.

Provider order is Mapbox → Photon: Mapbox when `MAPBOX_TOKEN` is set and
non-empty (the repo-wide variable name, see `app/config.py`), Photon
otherwise. The provider is chosen per call, not at import time, so a test can
switch it.

Both providers are called with `requests` (8 s timeout); the token is never
logged and never appears in an error message.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

MAPBOX_ATTRIBUTION = "© Mapbox © OpenStreetMap"
PHOTON_ATTRIBUTION = "© OpenStreetMap contributors"

MAPBOX_FORWARD_URL = "https://api.mapbox.com/search/geocode/v6/forward"
MAPBOX_REVERSE_URL = "https://api.mapbox.com/search/geocode/v6/reverse"
PHOTON_URL = "https://photon.komoot.io/api"
PHOTON_REVERSE_URL = "https://photon.komoot.io/api/reverse"

MAPBOX_TYPES = "address,street,place,locality,neighborhood"
TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class PlaceContext:
    """Geographic context of a place (country code/name, city, bbox, source).

    This is the provider-normalized place context referenced by the
    `geocoding.context` field. It is kept separate from `Suggestion` so a
    result can carry lightweight context without bloating every suggestion.
    """

    country_code: str
    country_name: str
    city: str
    bbox: tuple[float, float, float, float] | None
    source: str


@dataclass(frozen=True)
class Suggestion:
    """One normalized geocoding result (AC-8)."""

    id: str
    label: str
    lat: float
    lng: float
    type: str
    attribution: str
    context: PlaceContext | None = None


def _mapbox_token() -> str:
    """The Mapbox token, or "" when Mapbox is not configured."""
    return (os.environ.get("MAPBOX_TOKEN") or "").strip()


def _attribution(payload: dict[str, Any], fallback: str) -> str:
    """The provider's attribution string, or the fallback."""
    value = payload.get("attribution")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _parse_bbox(raw: Any) -> tuple[float, float, float, float] | None:
    """Parse a [west, south, east, north] sequence, or None when invalid."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        west, south, east, north = (float(v) for v in raw)
    except (TypeError, ValueError):
        return None
    if west > east or south > north:
        return None
    return (west, south, east, north)


def _parse_photon_extent(raw: Any) -> tuple[float, float, float, float] | None:
    """Photon `extent` is [west, north, east, south]; return (w, s, e, n)."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        west, north, east, south = (float(v) for v in raw)
    except (TypeError, ValueError):
        return None
    if west > east or south > north:
        return None
    return (west, south, east, north)


def _first_feature(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """The first GeoJSON feature of a provider payload, or None."""
    for feature in (payload or {}).get("features") or []:
        if isinstance(feature, dict):
            return feature
    return None


def _mapbox_feature_context(feature: dict[str, Any]) -> PlaceContext | None:
    """Derive a PlaceContext from a Mapbox v6 feature's own context."""
    props = feature.get("properties") or {}
    ctx = props.get("context")
    if not isinstance(ctx, dict):
        ctx = {}
    country = ctx.get("country") or {}
    country_code = str(country.get("country_code") or "").upper()
    country_name = str(country.get("name") or "")
    place = ctx.get("place") or ctx.get("locality") or {}
    city = str(place.get("name") or "")
    if not city and props.get("feature_type") in ("place", "locality"):
        city = str(props.get("name") or "")
    bbox = _parse_bbox(feature.get("bbox")) or _parse_bbox(props.get("bbox"))
    if not (country_code or country_name or city):
        return None
    return PlaceContext(
        country_code=country_code,
        country_name=country_name,
        city=city,
        bbox=bbox,
        source="place" if bbox else "country",
    )


def _photon_feature_context(feature: dict[str, Any]) -> PlaceContext | None:
    """Derive a PlaceContext from a Photon feature's own properties."""
    props = feature.get("properties") or {}
    country_code = str(props.get("countrycode") or "").upper()
    country_name = str(props.get("country") or "")
    city = str(props.get("city") or props.get("district") or "")
    bbox = _parse_photon_extent(props.get("extent")) or _parse_bbox(feature.get("bbox"))
    if not (country_code or country_name or city):
        return None
    return PlaceContext(
        country_code=country_code,
        country_name=country_name,
        city=city,
        bbox=bbox,
        source="place" if bbox else "country",
    )


def _mapbox_suggestions(payload: dict[str, Any]) -> list[Suggestion]:
    """Normalize a Mapbox Geocoding v6 response."""
    attribution = _attribution(payload, MAPBOX_ATTRIBUTION)
    out: list[Suggestion] = []
    for feature in payload.get("features") or []:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        coordinates = props.get("coordinates") or {}
        try:
            lat = float(coordinates["latitude"])
            lng = float(coordinates["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        label = props.get("full_address") or props.get("name") or ""
        if not label:
            continue
        out.append(
            Suggestion(
                id=str(feature.get("id") or props.get("mapbox_id") or ""),
                label=str(label),
                lat=lat,
                lng=lng,
                type=str(props.get("feature_type") or ""),
                attribution=attribution,
            )
        )
    return out


def _photon_suggestions(payload: dict[str, Any], country: str = "") -> list[Suggestion]:
    """Normalize a Photon GeoJSON response, optionally filtered by country."""
    attribution = _attribution(payload, PHOTON_ATTRIBUTION)
    out: list[Suggestion] = []
    for feature in payload.get("features") or []:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        if country and str(props.get("countrycode") or "").upper() != country:
            continue
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        try:
            lng = float(coordinates[0])
            lat = float(coordinates[1])
        except (IndexError, TypeError, ValueError):
            continue
        label = props.get("name") or ""
        if not label:
            continue
        osm_id = props.get("osm_id")
        osm_type = props.get("osm_type") or ""
        out.append(
            Suggestion(
                id=f"{osm_type}/{osm_id}" if osm_id else "",
                label=str(label),
                lat=lat,
                lng=lng,
                type=str(props.get("type") or ""),
                attribution=attribution,
            )
        )
    return out


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """GET a JSON object, or None on any transport/parse failure."""
    try:
        response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _search_mapbox(
    q: str,
    lat: float | None,
    lng: float | None,
    limit: int,
    *,
    country: str = "",
    bbox: tuple[float, float, float, float] | None = None,
) -> list[Suggestion]:
    params: dict[str, Any] = {
        "q": q,
        "access_token": _mapbox_token(),
        "types": MAPBOX_TYPES,
        "language": "en",
        "autocomplete": "true",
        "limit": max(1, min(int(limit), 10)),
    }
    if lat is not None and lng is not None:
        params["proximity"] = f"{lng},{lat}"
    if country:
        params["country"] = country.lower()
    if bbox is not None:
        params["bbox"] = ",".join(f"{value:.6f}" for value in bbox)
    payload = _get_json(MAPBOX_FORWARD_URL, params)
    if payload is None:
        return []
    return _mapbox_suggestions(payload)


def _reverse_mapbox(lat: float, lng: float) -> list[Suggestion]:
    payload = _get_json(
        MAPBOX_REVERSE_URL,
        {
            "longitude": lng,
            "latitude": lat,
            "access_token": _mapbox_token(),
            "types": MAPBOX_TYPES,
            "language": "en",
            "limit": 1,
        },
    )
    if payload is None:
        return []
    return _mapbox_suggestions(payload)


def _search_photon(
    q: str,
    lat: float | None,
    lng: float | None,
    limit: int,
    *,
    country: str = "",
    bbox: tuple[float, float, float, float] | None = None,
) -> list[Suggestion]:
    params: dict[str, Any] = {
        "q": q,
        "limit": max(1, min(int(limit), 20)),
        "lang": "en",
    }
    if lat is not None and lng is not None:
        params["lat"] = lat
        params["lon"] = lng
    if bbox is not None:
        params["bbox"] = ",".join(f"{value:.6f}" for value in bbox)
    payload = _get_json(PHOTON_URL, params)
    if payload is None:
        return []
    return _photon_suggestions(payload, country=country)


def _reverse_photon(lat: float, lng: float) -> list[Suggestion]:
    payload = _get_json(
        PHOTON_REVERSE_URL,
        {"lat": lat, "lon": lng, "limit": 1, "lang": "en"},
    )
    if payload is None:
        return []
    return _photon_suggestions(payload)


def search(
    q: str,
    lat: float | None = None,
    lng: float | None = None,
    limit: int = 5,
    *,
    country: str = "",
    bbox: tuple[float, float, float, float] | None = None,
) -> list[Suggestion]:
    """Forward geocode `q` into normalized suggestions.

    Uses Mapbox when `MAPBOX_TOKEN` is configured, Photon otherwise. Returns
    an empty list when the provider fails (fail soft: never raise).
    """
    query = (q or "").strip()
    if not query:
        return []
    # ROUTE_FIXTURES makes the whole route flow hermetic — the route endpoint
    # already honours it, but suggestions used to hit the live geocoder, so the
    # e2e dropdown was empty and auto-plan never fired (2026-11-25).
    from . import fixtures

    if fixtures.route_fixtures_enabled():
        try:
            fi_lat, fi_lng = fixtures.recorded_geocode(query)
        except ValueError:
            return []
        return [
            Suggestion(
                id=f"fixture:{query}",
                label=query,
                lat=fi_lat,
                lng=fi_lng,
                type="place",
                attribution="",
            )
        ]
    if _mapbox_token():
        return _search_mapbox(
            query, lat, lng, limit, country=country, bbox=bbox
        )
    return _search_photon(query, lat, lng, limit, country=country, bbox=bbox)


def reverse(lat: float, lng: float) -> list[Suggestion]:
    """Reverse geocode coordinates into normalized suggestions.

    Uses Mapbox when `MAPBOX_TOKEN` is configured, Photon otherwise. Returns
    an empty list when the provider fails (the caller falls back to a
    coordinate label).
    """
    if _mapbox_token():
        return _reverse_mapbox(lat, lng)
    return _reverse_photon(lat, lng)


_CONTEXT_CACHE: dict[tuple[float, float], PlaceContext] = {}


def _radius_bbox(lat: float, lng: float) -> tuple[float, float, float, float]:
    """A city-scale box around a point, clamped to valid coordinates."""
    dlat = 0.25
    dlng = 0.25 / max(0.2, abs(__import__("math").cos(__import__("math").radians(lat))))
    return (
        max(-180.0, lng - dlng),
        max(-90.0, lat - dlat),
        min(180.0, lng + dlng),
        min(90.0, lat + dlat),
    )


def _radius_context(
    lat: float,
    lng: float,
    country_code: str = "",
    country_name: str = "",
    city: str = "",
) -> PlaceContext:
    return PlaceContext(
        country_code=country_code,
        country_name=country_name,
        city=city,
        bbox=_radius_bbox(lat, lng),
        source="radius",
    )


def _mapbox_reverse_feature(lat: float, lng: float, types: str) -> dict[str, Any] | None:
    payload = _get_json(
        MAPBOX_REVERSE_URL,
        {
            "longitude": lng,
            "latitude": lat,
            "access_token": _mapbox_token(),
            "types": types,
            "language": "en",
            "limit": 1,
        },
    )
    return _first_feature(payload)


def _mapbox_city_bbox(city: str, country_code: str) -> tuple[float, float, float, float] | None:
    """Resolve a city's bbox with one forward place lookup.

    Mapbox reverse `place` is empty for some coordinates (Minsk returns the
    locality/district instead); the forward place feature carries the bbox.
    """
    if not city:
        return None
    params: dict[str, Any] = {
        "q": city,
        "access_token": _mapbox_token(),
        "types": "place",
        "language": "en",
        "limit": 1,
        "autocomplete": "false",
    }
    if country_code:
        params["country"] = country_code
    feature = _first_feature(_get_json(MAPBOX_FORWARD_URL, params))
    if feature is None:
        return None
    props = feature.get("properties") or {}
    return _parse_bbox(feature.get("bbox")) or _parse_bbox(props.get("bbox"))


def _context_mapbox(lat: float, lng: float) -> PlaceContext | None:
    """Country + city + city bbox from Mapbox reverse, with a forward fallback."""
    # 1. A place (city) feature is the exact answer and carries the bbox.
    place = _mapbox_reverse_feature(lat, lng, "place")
    if place is not None:
        ctx = _mapbox_feature_context(place)
        if ctx is not None:
            if ctx.bbox is None and ctx.city:
                bbox = _mapbox_city_bbox(ctx.city, ctx.country_code)
                if bbox is not None:
                    return PlaceContext(
                        country_code=ctx.country_code,
                        country_name=ctx.country_name,
                        city=ctx.city,
                        bbox=bbox,
                        source="place",
                    )
                return _radius_context(
                    lat, lng, ctx.country_code, ctx.country_name, ctx.city
                )
            return ctx

    # 2. Locality/district: the context names the city; resolve its bbox.
    locality = _mapbox_reverse_feature(lat, lng, "locality")
    if locality is not None:
        ctx = _mapbox_feature_context(locality)
        if ctx is not None:
            city_bbox = _mapbox_city_bbox(ctx.city, ctx.country_code) if ctx.city else None
            bbox = city_bbox or ctx.bbox
            if bbox is not None:
                return PlaceContext(
                    country_code=ctx.country_code,
                    country_name=ctx.country_name,
                    city=ctx.city,
                    bbox=bbox,
                    source="place" if city_bbox else "radius",
                )
            return _radius_context(lat, lng, ctx.country_code, ctx.country_name, ctx.city)

    # 3. Region (a city-level fallback in many countries), then country.
    region = _mapbox_reverse_feature(lat, lng, "region")
    if region is not None:
        ctx = _mapbox_feature_context(region)
        if ctx is not None:
            bbox = ctx.bbox
            if bbox is not None:
                return PlaceContext(
                    country_code=ctx.country_code,
                    country_name=ctx.country_name,
                    city=ctx.city,
                    bbox=bbox,
                    source="place",
                )
            return _radius_context(lat, lng, ctx.country_code, ctx.country_name, ctx.city)

    country = _mapbox_reverse_feature(lat, lng, "country")
    if country is not None:
        ctx = _mapbox_feature_context(country)
        if ctx is not None:
            return _radius_context(lat, lng, ctx.country_code, ctx.country_name, ctx.city)
    return None


def _context_photon(lat: float, lng: float) -> PlaceContext | None:
    """Photon place context: the city/place feature's extent, else radius."""
    payload = _get_json(
        PHOTON_REVERSE_URL,
        {"lat": lat, "lon": lng, "limit": 5, "lang": "en"},
    )
    if payload is None:
        return None
    for feature in payload.get("features") or []:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        country_code = str(props.get("countrycode") or "").upper()
        city = str(props.get("city") or props.get("name") or "")
        if not (country_code or city):
            continue
        country_name = str(props.get("country") or "")
        bbox = _parse_photon_extent(props.get("extent")) or _parse_bbox(feature.get("bbox"))
        if bbox is None:
            return _radius_context(lat, lng, country_code, country_name, city)
        return PlaceContext(
            country_code=country_code,
            country_name=country_name,
            city=city,
            bbox=bbox,
            source="place",
        )
    return None


def context(lat: float, lng: float) -> PlaceContext:
    """Resolve the place context (country code/name, city, bbox) for a point.

    Mapbox: a reverse `types=place` (exact city bbox when present), falling
    back to `types=locality,country` plus one cached forward `types=place`
    lookup for the city bbox. Photon: the city/place feature's extent. When
    the provider has no city box the result is a city-scale radius around the
    point (`source="radius"`); with no provider data at all the radius is
    recorded without a country (unrestricted). Cached by rounded coordinates.
    """
    from . import fixtures

    if fixtures.route_fixtures_enabled():
        return _radius_context(lat, lng)
    key = (round(float(lat), 3), round(float(lng), 3))
    cached = _CONTEXT_CACHE.get(key)
    if cached is not None:
        return cached
    if _mapbox_token():
        result = _context_mapbox(lat, lng)
    else:
        result = _context_photon(lat, lng)
    if result is None:
        result = _radius_context(lat, lng)
    _CONTEXT_CACHE[key] = result
    return result
