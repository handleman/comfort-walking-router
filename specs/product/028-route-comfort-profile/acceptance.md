# 028-route-comfort-profile — Acceptance

Generated: 2026-11-26T12:22:48Z · Verdict: **PASS** (0 failed · 3 passed · 0 unverified · 3 n/a)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | PASS | probe | /route request fired |
| AC-2 | PASS | probe | /route request fired |
| AC-3 | N/A | declared | honest gap when the corridor is unavailable — backend behaviour |
| AC-4 | PASS | probe | found 1 element(s); count 3 >= 3; found 1 element(s) |
| AC-5 | N/A | declared | pytest/ruff/mypy gates |
| AC-6 | N/A | declared | documentation |

## Oracle self-test

| AC | Kind | Verdict | Detail |
| --- | --- | --- | --- |
| AC-1 | route_request | OK | error: page.fill: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('input[placeholder=\'e.g. Englischer Garten\']')[22m  (after removing 1 node(s)) |
| AC-2 | route_request | OK | error: page.fill: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('input[placeholder=\'e.g. Englischer Garten\']')[22m  (after removing 1 node(s)) |
| AC-4 | exists | OK | not found (after removing 1 node(s)) |
| AC-4 | min_count | OK | count 0 >= 3 (after removing 3 node(s)) |
| AC-4 | exists | OK | not found (after removing 1 node(s)) |

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
