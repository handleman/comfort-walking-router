# 014-walk-guidance-ux — Acceptance

Generated: 2026-11-28T13:14:39Z · Verdict: **PASS** (0 failed · 7 passed · 0 unverified · 2 n/a · 0 e2e)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | PASS | probe | start-location dialog shown on denied geolocation |
| AC-2 | PASS | probe | /route request fired; clicked; count 1 vs expect 1; found 1 element(s) |
| AC-3 | PASS | probe | found 1 element(s); found 1 element(s) |
| AC-4 | PASS | probe | /route request fired |
| AC-5 | PASS | probe | /route request fired |
| AC-6 | PASS | probe | marker moved after a new geolocation fix |
| AC-7 | N/A | declared | arrival needs walking into the radius; the e2e suite drives the fix sequence |
| AC-8 | PASS | probe | "pk." absent |
| AC-9 | N/A | declared | gates/documentation |

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
