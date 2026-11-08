import hashlib
from datetime import UTC, datetime
from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .cache import Cache
from .geocoder import geocode_place
from .providers.osrm import OSRMProvider
from .scoring import score_comfort

app = FastAPI(title="Comfort Walking Router")
cache = Cache()
osrm = OSRMProvider()



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


def _route_id(start: str, end: str, preference: str | None) -> str:
    key = f"{start}|{end}|{preference or ''}"
    return hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:12]


def _build_response(
    body: RouteRequest,
    start: tuple[float, float],
    end: tuple[float, float],
    route: dict[str, Any],
) -> RouteResponse:
    feature = route["features"][0]
    geometry = feature["geometry"]
    distance_m = float(feature["properties"]["distance"])
    duration_s = float(feature["properties"]["duration"])
    preference_note = (
        PREFERENCE_NOTES[body.preference] if body.preference else BALANCED_NOTE
    )
    props = feature.get("properties", {})
    comfort_score = score_comfort(props, body.preference or "balanced")
    
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
        duration_s=duration_s
    )


@app.post("/route", response_model=RouteResponse)
def route(body: RouteRequest) -> RouteResponse:
    cached = cache.get((body.start, body.end, body.preference))
    if cached is not None:
        return RouteResponse.model_validate(cached)
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
    response = _build_response(body, start, end, raw_route)
    cache.set((body.start, body.end, body.preference), response.model_dump())
    return response
