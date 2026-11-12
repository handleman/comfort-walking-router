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
class Suggestion:
    """One normalized geocoding result (AC-8)."""

    id: str
    label: str
    lat: float
    lng: float
    type: str
    attribution: str


def _mapbox_token() -> str:
    """The Mapbox token, or "" when Mapbox is not configured."""
    return (os.environ.get("MAPBOX_TOKEN") or "").strip()


def _attribution(payload: dict[str, Any], fallback: str) -> str:
    """The provider's attribution string, or the fallback."""
    value = payload.get("attribution")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


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


def _photon_suggestions(payload: dict[str, Any]) -> list[Suggestion]:
    """Normalize a Photon GeoJSON response."""
    attribution = _attribution(payload, PHOTON_ATTRIBUTION)
    out: list[Suggestion] = []
    for feature in payload.get("features") or []:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
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


def _search_mapbox(q: str, lat: float | None, lng: float | None, limit: int) -> list[Suggestion]:
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


def _search_photon(q: str, lat: float | None, lng: float | None, limit: int) -> list[Suggestion]:
    params: dict[str, Any] = {
        "q": q,
        "limit": max(1, min(int(limit), 20)),
        "lang": "en",
    }
    if lat is not None and lng is not None:
        params["lat"] = lat
        params["lon"] = lng
    payload = _get_json(PHOTON_URL, params)
    if payload is None:
        return []
    return _photon_suggestions(payload)


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
) -> list[Suggestion]:
    """Forward geocode `q` into normalized suggestions.

    Uses Mapbox when `MAPBOX_TOKEN` is configured, Photon otherwise. Returns
    an empty list when the provider fails (fail soft: never raise).
    """
    query = (q or "").strip()
    if not query:
        return []
    if _mapbox_token():
        return _search_mapbox(query, lat, lng, limit)
    return _search_photon(query, lat, lng, limit)


def reverse(lat: float, lng: float) -> list[Suggestion]:
    """Reverse geocode coordinates into normalized suggestions.

    Uses Mapbox when `MAPBOX_TOKEN` is configured, Photon otherwise. Returns
    an empty list when the provider fails (the caller falls back to a
    coordinate label).
    """
    if _mapbox_token():
        return _reverse_mapbox(lat, lng)
    return _reverse_photon(lat, lng)
