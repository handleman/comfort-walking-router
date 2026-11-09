import hashlib
import logging
from datetime import UTC, datetime
from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import saved_routes
from .cache import Cache
from .geocoder import geocode_place
from .preferences import auto_preference
from .providers.open_meteo import OpenMeteoProvider
from .providers.osrm import OSRMProvider
from .scoring import score_comfort
from .weather_cache import WeatherCache

app = FastAPI(title="Comfort Walking Router")
app.include_router(saved_routes.router)
cache = Cache()
osrm = OSRMProvider()
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
    504: "gateway_timeout",
}


class RouteRequest(BaseModel):
    start: str = Field(min_length=1)
    end: str = Field(min_length=1)
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
        explanation=explanation,
        geometry=geometry,
        distance_m=distance_m,
        duration_s=duration_s,
        applied_preference=applied_preference,
        preference_source=preference_source,
        weather=weather,
    )


@app.post("/route", response_model=RouteResponse)
def route(body: RouteRequest) -> RouteResponse:
    global cache_hits, provider_calls

    cached = cache.get((body.start, body.end, body.preference))
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
        start = geocode_place(body.start)
        end = geocode_place(body.end)
        raw_route = osrm.route(start, end, preference=body.preference)
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
        if auto is not None:
            applied_preference = auto
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
    cache.set((body.start, body.end, body.preference), response.model_dump())
    return response
