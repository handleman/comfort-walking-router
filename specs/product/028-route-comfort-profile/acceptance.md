# 028-route-comfort-profile — Acceptance

Generated: 2026-11-28T14:15:40Z · Verdict: **PASS** (0 failed · 2 passed · 0 unverified · 4 n/a · 0 e2e)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | PASS | probe | /route request fired |
| AC-2 | N/A | declared | the corridor fetch count / cache hit is a backend assertion (tests/test_route_comfort.py); the DOM cannot observe it |
| AC-3 | N/A | declared | honest gap when the corridor is unavailable — backend behaviour |
| AC-4 | PASS | probe | found 1 element(s); count 5 >= 3; found 1 element(s) |
| AC-5 | N/A | declared | pytest/ruff/mypy gates |
| AC-6 | N/A | declared | documentation |

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
