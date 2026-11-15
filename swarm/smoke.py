"""`make smoke-live` — exercise the real providers, no fixtures.

The human gates (001 AC-2 live demo, 007 AC-8 real GPS) cannot be automated end
to end, but everything before the walker's eyes can be: this posts one real
route from München and prints the distance, the comfort score, the profile and
the weather the app used. A 200 with a real profile is the code half of the gate;
looking at the map is the human half.

Exit code: 0 on a usable route, 1 otherwise (so it can be a gate later).
"""

from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    os.environ.pop("ROUTE_FIXTURES", None)  # real providers only
    sys.path.insert(0, REPO)
    from fastapi.testclient import TestClient

    from app import main as app_main

    body = {
        "start": os.getenv("SMOKE_START", "Marienplatz, Munich"),
        "end": os.getenv("SMOKE_END", "Englischer Garten, Munich"),
        "preference": os.getenv("SMOKE_PREFERENCE", "hot"),
    }
    with TestClient(app_main.app) as client:
        response = client.post("/route", json=body)
    if response.status_code != 200:
        print(f"smoke-live FAILED: {response.status_code} {response.text[:300]}")
        return 1
    payload = response.json()
    profile = payload.get("comfort_profile") or []
    print(f"route      {round(payload['distance_m'])} m, {round(payload['duration_s'] / 60)} min")
    print(f"comfort    {payload['comfort_score']} ({len(profile)} segments)")
    print(f"weather    {json.dumps(payload.get('weather'))}")
    for line in payload["explanation"][:6]:
        print(f"  - {line}")
    if not profile:
        print("smoke-live: no comfort profile (OSM data gap) — code path works, data did not")
        return 1
    print("smoke-live OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
