# 028-route-comfort-profile — Acceptance

Generated: 2026-11-26T13:17:28Z · Verdict: **FAIL** (2 failed · 1 passed · 0 unverified · 3 n/a)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | FAIL | probe | error: page.fill: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('input[placeholder=\'e.g. Marienplatz, Munich\']')[22m |
| AC-2 | FAIL | probe | error: page.fill: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('input[placeholder=\'e.g. Marienplatz, Munich\']')[22m |
| AC-3 | N/A | declared | honest gap when the corridor is unavailable — backend behaviour |
| AC-4 | PASS | probe | found 1 element(s); count 3 >= 3; found 1 element(s) |
| AC-5 | N/A | declared | pytest/ruff/mypy gates |
| AC-6 | N/A | declared | documentation |

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
