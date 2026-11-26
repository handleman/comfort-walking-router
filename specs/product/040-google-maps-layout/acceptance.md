# 040-google-maps-layout — Acceptance

Generated: 2026-11-26T13:41:37Z · Verdict: **PASS** (0 failed · 8 passed · 0 unverified · 0 n/a)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | PASS | probe | found 1 element(s); found 1 element(s); count 24 >= 1 |
| AC-2 | PASS | probe | found 1 element(s); found 1 element(s); found 1 element(s); found 1 element(s); absent |
| AC-3 | PASS | probe | found 1 element(s); absent |
| AC-4 | PASS | probe | count 0 vs expect 0; count 0 vs expect 0 |
| AC-5 | PASS | probe | found 1 element(s) |
| AC-6 | PASS | probe | count 7 >= 3; count 6 >= 3 |
| AC-7 | PASS | probe | 0 console error(s); 0 console error(s) |
| AC-8 | PASS | probe | /route request fired |

## Oracle self-test

| AC | Kind | Verdict | Detail |
| --- | --- | --- | --- |
| AC-1 | exists | OK | not found (after removing 1 node(s)) |
| AC-1 | min_count | OK | count 0 >= 1 (after removing 24 node(s)) |
| AC-2 | exists | OK | not found (after removing 1 node(s)) |
| AC-2 | exists | OK | not found (after removing 1 node(s)) |
| AC-2 | absent | UNSUPPORTED | nothing to remove (absent/count=0) |
| AC-3 | exists | OK | not found (after removing 1 node(s)) |
| AC-3 | absent | UNSUPPORTED | nothing to remove (absent/count=0) |
| AC-4 | count | UNSUPPORTED | nothing to remove (absent/count=0) |
| AC-5 | exists | OK | not found (after removing 1 node(s)) |
| AC-6 | min_count | OK | count 0 >= 3 (after removing 7 node(s)) |
| AC-7 | console_errors | OK | 1 console error(s): acceptance selftest |
| AC-8 | route_request | OK | error: page.fill: Timeout 30000ms exceeded. Call log: [2m  - waiting for locator('input[placeholder=\'e.g. Englischer Garten\']')[22m  (after removing 1 node(s)) |

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
