# 014-walk-guidance-ux — Acceptance

Generated: 2026-11-26T12:22:48Z · Verdict: **PASS** (0 failed · 3 passed · 0 unverified · 6 n/a)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | N/A | declared | permission grant/deny needs the browser permission harness |
| AC-2 | N/A | declared | glyph is a map divIcon, asserted by the e2e suite |
| AC-3 | PASS | probe | found 1 element(s); found 1 element(s) |
| AC-4 | PASS | probe | /route request fired |
| AC-5 | PASS | probe | /route request fired |
| AC-6 | N/A | declared | moving marker needs a walk session |
| AC-7 | N/A | declared | arrival needs walking into the radius |
| AC-8 | N/A | declared | token discipline is a bundle/request assertion |
| AC-9 | N/A | declared | gates/documentation |

## Oracle self-test

| AC | Kind | Verdict | Detail |
| --- | --- | --- | --- |
| AC-3 | exists | OK | not found (after removing 1 node(s)) |
| AC-4 | route_request | OK | error: page.fill: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('input[placeholder=\'e.g. Englischer Garten\']')[22m  (after removing 1 node(s)) |
| AC-5 | route_request | OK | error: page.fill: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('input[placeholder=\'e.g. Englischer Garten\']')[22m  (after removing 1 node(s)) |

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
