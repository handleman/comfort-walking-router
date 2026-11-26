# 028-route-comfort-profile — Acceptance

Generated: 2026-11-26T10:02:11Z · Verdict: **FAIL** (1 failed · 2 passed · 3 unverified)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | PASS | probe | /route request fired |
| AC-2 | PASS | probe | /route request fired |
| AC-3 | UNVERIFIED | none | unclear |
| AC-4 | FAIL | probe | found 1 element(s); not found; count 3 >= 3; count 0 >= 3; found 1 element(s) |
| AC-5 | UNVERIFIED | none | unclear |
| AC-6 | UNVERIFIED | none | unclear |

## Configuration

- **WARN** no acceptance.toml check for AC-3, AC-5, AC-6

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
