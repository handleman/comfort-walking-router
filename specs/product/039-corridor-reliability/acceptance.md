# 039-corridor-reliability — Acceptance

Generated: 2026-11-26T10:02:11Z · Verdict: **FAIL** (1 failed · 0 passed · 2 unverified)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | FAIL | probe | /route request fired; text matches; error: locator.textContent: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('section.route-summary')[22m |
| AC-2 | UNVERIFIED | none | unclear |
| AC-3 | UNVERIFIED | none | unclear |

## Configuration

- **WARN** no acceptance.toml check for AC-2, AC-3

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
