"""050: live Overpass corridor probe — the three mirrors, no human in the loop.

A fixed Munich route is fetched from each mirror in order, so a run answers
"is the corridor healthy right now, and which mirror served it?" without opening
a browser. Deterministic tests exercise `probe()` with an injected fetch; the
network path is the same one `app.comfort` uses.

    make corridor-check            # human-readable JSON + exit 0/1
    python -m swarm.corridor_check
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any

MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

# A fixed, short Munich route (Marienplatz → Englischer Garten) so successive
# probes compare like-for-like.
GEOMETRY: dict[str, Any] = {
    "type": "LineString",
    "coordinates": [[11.5755, 48.1374], [11.6056, 48.1642]],
}


def probe(*, fetch: Callable[..., list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Hit each mirror in order; report per-mirror status and the corridor result."""
    from app import comfort

    if fetch is None:
        from app.providers import overpass as _overpass

        fetch = _overpass.fetch_overpass_features

    try:
        box = comfort.corridor_bbox(GEOMETRY)
        query = comfort.overpass_query(box)
    except Exception as exc:  # noqa: BLE001 - a bad geometry is a probe failure, not a crash
        return {"route": "munich-fixed", "corridor": False, "error": str(exc)[:200], "mirrors": []}

    mirrors: list[dict[str, Any]] = []
    serving = None
    for url in MIRRORS:
        started = time.monotonic()
        try:
            features = fetch(url, query=query)
        except Exception as exc:  # noqa: BLE001 - a failed mirror is data, not a crash
            mirrors.append(
                {
                    "mirror": url,
                    "ok": False,
                    "error": str(exc)[:200],
                    "ms": round((time.monotonic() - started) * 1000),
                }
            )
            continue
        ms = round((time.monotonic() - started) * 1000)
        ok = bool(features)
        mirrors.append({"mirror": url, "ok": ok, "features": len(features or []), "ms": ms})
        if ok:
            serving = url
            break

    # One round only: an answering mirror is the reliability signal. The app
    # computes the full factors when it actually routes; re-fetching here would
    # double the probe's worst-case time (3 x the HTTP timeout).
    return {
        "route": "munich-fixed",
        "corridor": serving is not None,
        "serving_mirror": serving,
        "mirrors": mirrors,
    }


def main() -> int:
    # A probe must talk to the network: fixtures would make it always green.
    os.environ.pop("ROUTE_FIXTURES", None)
    result = probe()
    print(json.dumps(result, indent=2, default=str), flush=True)
    if not result.get("corridor"):
        print(f"corridor-check: FAIL — no mirror served a corridor (tried {len(MIRRORS)})", flush=True)
        return 1
    print(f"corridor-check: OK — served by {result.get('serving_mirror')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
