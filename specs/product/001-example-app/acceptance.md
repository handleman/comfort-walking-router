# 001-example-app — Acceptance

Generated: 2026-11-26T12:22:48Z · Verdict: **PASS** (0 failed · 2 passed · 0 unverified · 2 n/a)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | PASS | probe | /route request fired; found 1 element(s) |
| AC-2 | PASS | probe | text matches |
| AC-3 | N/A | declared | SQLite cache: backend behaviour, no browser surface |
| AC-4 | N/A | declared | pytest/ruff/mypy gates |

## Oracle self-test

| AC | Kind | Verdict | Detail |
| --- | --- | --- | --- |
| AC-1 | route_request | OK | error: page.fill: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('input[placeholder=\'e.g. Englischer Garten\']')[22m  (after removing 1 node(s)) |
| AC-1 | exists | OK | not found (after removing 1 node(s)) |
| AC-2 | text | OK | error: locator.textContent: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('section.route-summary')[22m  (after removing 1 node(s)) |

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
