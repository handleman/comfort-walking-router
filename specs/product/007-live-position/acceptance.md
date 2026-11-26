# 007-live-position — Acceptance

Generated: 2026-11-26T13:41:37Z · Verdict: **PASS** (0 failed · 1 passed · 0 unverified · 7 n/a)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | PASS | probe | /route request fired; clicked; visible |
| AC-2 | N/A | declared | simulated movement needs a walk session over time |
| AC-3 | N/A | declared | permission denial needs the browser permission harness |
| AC-4 | N/A | declared | sustained drift needs a moving fix sequence |
| AC-5 | N/A | declared | reroute-query interaction |
| AC-6 | N/A | declared | auto-center toggle interaction |
| AC-7 | N/A | declared | arrival needs walking into the radius |
| AC-8 | N/A | declared | pytest/ruff/mypy gates |

## Oracle self-test

| AC | Kind | Verdict | Detail |
| --- | --- | --- | --- |
| AC-1 | route_request | OK | error: page.fill: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('input[placeholder=\'e.g. Englischer Garten\']')[22m  (after removing 1 node(s)) |
| AC-1 | click | OK | error: locator.click: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('[data-testid=\'start-walk\']')[22m  (after removing 1 node(s)) |
| AC-1 | wait_for | UNSUPPORTED | interaction check; mutation would only time out |

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
