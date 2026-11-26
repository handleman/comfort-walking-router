# 028-route-comfort-profile — Acceptance

Generated: 2026-11-26T13:26:21Z · Verdict: **FAIL** (1 failed · 2 passed · 0 unverified · 3 n/a)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | PASS | probe | /route request fired |
| AC-2 | FAIL | probe | no /route request |
| AC-3 | N/A | declared | honest gap when the corridor is unavailable — backend behaviour |
| AC-4 | PASS | probe | found 1 element(s); count 3 >= 3; found 1 element(s) |
| AC-5 | N/A | declared | pytest/ruff/mypy gates |
| AC-6 | N/A | declared | documentation |

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
