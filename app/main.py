
import requests
from fastapi import FastAPI, HTTPException, Query

from .cache import Cache
from .geocoder import geocode_place
from .providers.osrm import OSRMProvider

cache = Cache()
osrm = OSRMProvider()
app = FastAPI()


@app.get("/route")
def route(start: str, end: str, preference: str | None = Query(default=None)) -> dict:
    try:
        # Cache check at start of route endpoint
        cached_response = cache.get((start, end, preference))
        if cached_response is not None:
            return cached_response
        start_loc = geocode_place(start)
        end_loc = geocode_place(end)
        response = osrm.route((start_loc[0], start_loc[1]), (end_loc[0], end_loc[1]), preference=preference)
        cache.set((start, end, preference), response)
        return response
    except requests.RequestException:
        raise HTTPException(status_code=504, detail="Upstream routing request failed")
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e!s}")
