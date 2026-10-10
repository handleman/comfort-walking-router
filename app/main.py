import requests
from fastapi import FastAPI, HTTPException

from .geocoder import geocode_place
from .providers.osrm import OSRMProvider

osrm = OSRMProvider()
app = FastAPI()


@app.get("/route")
def route(start: str, end: str) -> dict:
    try:
        start_loc = geocode_place(start)
        end_loc = geocode_place(end)
        return osrm.route(start_loc, end_loc)
    except requests.RequestException:
        raise HTTPException(status_code=504, detail="Upstream routing request failed")
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e!s}")
