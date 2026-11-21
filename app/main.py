import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import comfort, fixtures, geocode_cache, geocoding, saved_routes
from . import db as app_db
from .cache import Cache
from .config import get_mapbox_token
from .geocoder import geocode_place
from .preferences import auto_preference
from .providers.mapbox import MapboxProvider
from .providers.open_meteo import OpenMeteoProvider
from .scoring import score_comfort
from .weather_cache import WeatherCache

app = FastAPI(title="Comfort Walking Router")
app.include_router(saved_routes.router)


@app.on_event("startup")
def _migrate_schema() -> None:
    """Run saved-routes migrations at boot when a database is configured (035),
    so a Render/Neon `DATABASE_URL` works without a separate migrate step. A
    missing/unreachable DB is logged, not fatal — route/geocode do not need it."""
    if not app_db.DATABASE_URL:
        return
    try:
        app_db.run_migrations()
    except Exception as exc:  # noqa: BLE001 - a down DB is a data gap, not a crash
        logging.getLogger(__name__).warning("saved-routes migrations skipped: %s", exc)
cache = Cache()
mapbox = MapboxProvider(access_token=get_mapbox_token())
open_meteo = OpenMeteoProvider()
weather_cache = WeatherCache()

# Calls-vs-cache-hits counters for /route cache logging (AC-3).
cache_hits = 0
provider_calls = 0

# Calls-vs-cache-hits counters for /route cache logging (AC-3).
cache_hits = 0
provider_calls = 0


def _get_weather(midpoint: tuple[float, float]) -> dict[str, Any] | None:
    """Return cached weather for the midpoint, fetching from Open-Meteo on miss."""
    weather_cache = WeatherCache()
    cached = weather_cache.get(midpoint)
    if cached is not None:
        return cached
    fetched = OpenMeteoProvider().fetch(midpoint)
    if fetched is not None:
        weather_cache.set(midpoint, fetched)
    return fetched



PREFERENCE_NOTES = {
    "hot": "Hot preference: shaded, greener streets preferred.",
    "cloudy": "Cloudy preference: sunnier, open streets preferred.",
    "quiet": "Quiet preference: low-traffic, peaceful streets preferred.",
}
BALANCED_NOTE = "No preference: balanced comfort."

ERROR_CODES = {
    404: "not_found",
    422: "validation_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "gateway_timeout",
}


class RouteRequest(BaseModel):
    start: str = Field(min_length=1)
    end: str = Field(min_length=1)
    start_coords: tuple[float, float] | None = None
    end_coords: tuple[float, float] | None = None
    preference: Literal["hot", "cloudy"] | None = None
    prefer_lit: bool = Field(default=False)
    avoid_traffic: bool = Field(default=False)


class Waypoint(BaseModel):
    lat: float
    lng: float


class RouteResponse(BaseModel):
    id: str
    name: str
    description: str
    waypoints: list[Waypoint]
    status: str
    timestamp: str
    comfort_score: float
    comfort_profile: list[dict[str, Any]] | None = None
    explanation: list[str]
    geometry: dict[str, Any]
    distance_m: float
    duration_s: float
    applied_preference: str | None = None
    preference_source: Literal["auto", "manual"] | None = None
    weather: dict[str, Any] | None = None


@app.exception_handler(HTTPException)
def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": ERROR_CODES.get(exc.status_code, "error"),
            "message": str(exc.detail),
        },
    )


@app.exception_handler(RequestValidationError)
def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "Invalid request body",
            "details": exc.errors(),
        },
    )


def _route_id(
    start: str,
    end: str,
    preference: str | None,
    prefer_lit: bool = False,
    avoid_traffic: bool = False,
) -> str:
    key = f"{start}|{end}|{preference or ''}|{prefer_lit}|{avoid_traffic}"
    return hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:12]


def _build_response(
    body: RouteRequest,
    start: tuple[float, float],
    end: tuple[float, float],
    route: dict[str, Any],
    applied_preference: str | None = None,
    preference_source: Literal["auto", "manual"] | None = None,
    weather: dict[str, Any] | None = None,
) -> RouteResponse:
    feature = route["features"][0]
    geometry = feature["geometry"]
    distance_m = float(feature["properties"]["distance"])
    duration_s = float(feature["properties"]["duration"])
    preference_note = (
        PREFERENCE_NOTES[body.preference] if body.preference else BALANCED_NOTE
    )
    props = feature.get("properties", {})
    # 001 AC-2: real OSM corridor factors (best effort). Nothing downstream is
    # rejected when Overpass is unavailable; the explanation says so instead of
    # naming factors the route never had.
    corridor = comfort.corridor_data(geometry)
    comfort_data = corridor["factors"] if corridor else None
    if comfort_data:
        props = {**props, **comfort_data}
    profile = comfort.profile(
        geometry,
        comfort_data,
        feature_points_in=(corridor or {}).get("feature_points"),
        total_m=distance_m,
        preference=applied_preference or body.preference or "balanced",
    )
    if profile:
        # 028 AC-1: the number is the picture's mean, by construction.
        comfort_score = round(comfort.weighted_score(profile), 1)
    else:
        # No OSM corridor: fall back to the weather/tag score, and the
        # explanation says the profile is unavailable (AC-3).
        comfort_score = score_comfort(
            props,
            body.preference or "balanced",
            prefer_lit=body.prefer_lit,
            avoid_traffic=body.avoid_traffic,
        )

    # Build explanation with applied factors
    explanation = [
        f"{distance_m / 1000:.2f} km, about {round(duration_s / 60)} min walking.",
        preference_note,
        "Comfort factor: applied based on preference and route properties.",
    ]
    if weather:
        # The weather is a factor of every score, whatever chose the preference,
        # so the explanation states it once (004 AC-2).
        explanation.append(
            f"Weather: {weather.get('temperature')}°C, "
            f"cloud cover {weather.get('cloud_cover')}%."
        )
    if preference_source == "auto" and weather:
        # 004 AC-2: an automatic preference must show its reason, not just its
        # name — the e2e asserts the factor that decided it.
        explanation.append(
            "Auto preference: cloud cover "
            f"{weather.get('cloud_cover')}% and {weather.get('temperature')}°C "
            f"→ {applied_preference}."
        )
    if profile:
        shaded = [s for s in profile if s.factor == "shade"]
        sunny = [s for s in profile if s.factor == "sun"]
        span = f"{profile[0].from_m:.0f}–{profile[-1].to_m:.0f} m"
        explanation.append(
            f"Profile: {len(shaded)} of {len(profile)} segments shaded, "
            f"{len(sunny)} sunny ({span})."
        )
    else:
        explanation.append("Profile: unavailable without OSM corridor data.")
    data = comfort_data or {}
    shade_value = data.get("shade_factor")
    quiet_value = data.get("quiet_factor")
    if isinstance(shade_value, (int, float)) and isinstance(quiet_value, (int, float)):
        explanation.append(
            "Comfort data: OSM corridor — "
            f"shade {float(shade_value):.2f}, quiet {float(quiet_value):.2f}, "
            f"{data.get('osm_ways', 0)} ways, "
            f"{data.get('osm_trees', 0)} trees."
        )
    else:
        explanation.append(
            "Comfort data: OSM corridor unavailable — weather-only score (data gap)."
        )

    # Add preference-specific factors
    if body.preference == "hot":
        explanation.append(f"Shade factor: {'high' if props.get('shade_factor', 0) > 0.5 else 'low'}")
        explanation.append(f"Sun factor: {'reduced' if props.get('sun_factor', 1) < 0.7 else 'normal'}")
    elif body.preference == "cloudy":
        explanation.append(f"Sun factor: {'high' if props.get('sun_factor', 0) > 0.5 else 'low'}")
        explanation.append(f"Shade factor: {'reduced' if props.get('shade_factor', 1) < 0.7 else 'normal'}")
    elif body.preference == "quiet":
        explanation.append(f"Quiet factor: {'high' if props.get('quiet_factor', 0) > 0.5 else 'low'}")
        explanation.append(f"Noise level: {'quiet' if props.get('noise_level', 50) < 45 else 'moderate'}")
    else:
        explanation.append(f"Shade factor: {'high' if props.get('shade_factor', 0) > 0.5 else 'low'}")
        explanation.append(f"Sun factor: {'reduced' if props.get('sun_factor', 1) < 0.7 else 'normal'}")
        explanation.append(f"Noise level: {'quiet' if props.get('noise_level', 50) < 45 else 'moderate'}")

    # Lit/traffic explanation entries (AC-1)
    if body.prefer_lit:
        explanation.append(
            f"Lighting: {'well lit' if props.get('lit') == 'yes' else 'not lit'}"
        )
    if body.avoid_traffic:
        highway = props.get("highway")
        if highway in ("primary", "secondary", "trunk"):
            explanation.append("Traffic: busy road, penalized")
        elif highway in ("residential", "footway", "path"):
            explanation.append("Traffic: quiet way, bonus applied")
        else:
            explanation.append("Traffic: no road class data")
    
    return RouteResponse(
        id=_route_id(body.start, body.end, body.preference),
        name=f"{body.start} → {body.end}",
        description=f"Walking route from {body.start} to {body.end}",
        waypoints=[
            Waypoint(lat=start[0], lng=start[1]),
            Waypoint(lat=end[0], lng=end[1]),
        ],
        status="active",
        timestamp=datetime.now(tz=UTC).isoformat(),
        comfort_score=comfort_score,
        comfort_profile=[segment.as_dict() for segment in profile] if profile else None,
        explanation=explanation,
        geometry=geometry,
        distance_m=distance_m,
        duration_s=duration_s,
        applied_preference=applied_preference,
        preference_source=preference_source,
        weather=weather,
    )


@app.get("/geocode")
def geocode_endpoint(
    q: str = Query(min_length=2, max_length=120),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(5, ge=1, le=10),
):
    key = f"fwd:{q.strip().lower()}:{lat}:{lng}:{limit}"
    cached = geocode_cache.get(key)
    if cached is not None:
        return {"suggestions": cached}
    results = geocoding.search(q, lat, lng, limit)
    geocode_cache.set(key, results)
    return {"suggestions": results}


@app.get("/geocode/reverse")
def reverse_geocode_endpoint(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
):
    key = f"rev:{lat}:{lng}"
    cached = geocode_cache.get(key)
    if cached is not None:
        return {"suggestions": cached}
    results = geocoding.reverse(lat, lng)
    geocode_cache.set(key, results)
    return {"suggestions": results}


@app.post("/route", response_model=RouteResponse)
def route(body: RouteRequest) -> RouteResponse:
    global cache_hits, provider_calls

    cache_key = (
        body.start,
        body.end,
        body.preference,
        body.start_coords,
        body.end_coords,
    )
    cached = cache.get(cache_key)
    if cached is not None:
        cache_hits += 1
        logging.getLogger(__name__).info(
            "route cache hit, skipping provider: "
            f"{body.start}|{body.end}|{body.preference}"
        )
        return RouteResponse.model_validate(cached)
    provider_calls += 1
    logging.getLogger(__name__).info(
        "route cache miss, calling provider: "
        f"{body.start}|{body.end}|{body.preference}"
    )
    try:
        if body.start_coords is not None and body.end_coords is not None:
            start = body.start_coords
            end = body.end_coords
            if fixtures.route_fixtures_enabled():
                raw_route = fixtures.recorded_route(
                    start, end, preference=body.preference
                )
            else:
                raw_route = mapbox.route(start, end, preference=body.preference)
        elif fixtures.route_fixtures_enabled():
            start = fixtures.recorded_geocode(body.start)
            end = fixtures.recorded_geocode(body.end)
            raw_route = fixtures.recorded_route(
                start, end, preference=body.preference
            )
        else:
            start = geocode_place(body.start)
            end = geocode_place(body.end)
            raw_route = mapbox.route(start, end, preference=body.preference)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=504, detail="Upstream routing request failed"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=502, detail=f"Upstream response missing {exc}"
        ) from exc
    midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    weather: dict[str, Any] | None = None
    try:
        weather = _get_weather(midpoint)
    except Exception:  # noqa: BLE001 - weather is best-effort; fall back to caller
        weather = None
    applied_preference: str | None = None
    preference_source: Literal["auto", "manual"] | None = None
    if body.preference is not None:
        applied_preference = body.preference
        preference_source = "manual"
    elif weather is not None:
        auto = auto_preference(weather, body.preference)
        # 004/005: when the weather matches neither rule, the honest answer is
        # "balanced", not null — the UI rendered "Auto: null 6.6°C" (2026-11-15).
        applied_preference = auto or "balanced"
        preference_source = "auto"
    else:
        # Total failure (no caller preference, no weather): fall back to balanced.
        applied_preference = "balanced"
    response = _build_response(
        body,
        start,
        end,
        raw_route,
        applied_preference=applied_preference,
        preference_source=preference_source,
        weather=weather,
    )
    cache.set(cache_key, response.model_dump())
    return response


# 035: serve the built Svelte app from the same origin as the API, so one free
# Render service hosts both (no CORS, no proxy). The API routes above are
# registered first, so `/route`, `/geocode` and `/saved-routes` keep winning; the
# mount only catches everything else. A no-op when dist/ was never built
# (`make dev` runs vite; the tests do not build dist/).
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (_frontend_dist / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
