# 040-google-maps-layout — Acceptance

Generated: 2026-11-25T22:36:07Z · Verdict: **FAIL** (2 failed · 6 passed · 0 unverified)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | PASS | probe | found 1 element(s); found 1 element(s); count 24 >= 1 |
| AC-2 | PASS | probe | found 1 element(s); found 1 element(s); found 1 element(s); found 1 element(s); absent |
| AC-3 | PASS | probe | found 1 element(s); absent |
| AC-4 | PASS | probe | count 0 vs expect 0; count 0 vs expect 0 |
| AC-5 | PASS | probe | found 1 element(s) |
| AC-6 | PASS | probe | count 7 >= 3; count 6 >= 3 |
| AC-7 | FAIL | probe | found 2 element(s); absent |
| AC-8 | FAIL | probe | error: locator.waitFor: Timeout 8000ms exceeded. Call log: [2m  - waiting for locator('[role="option"]').first() to be visible[22m |

## Global checks

- **FAIL** desktop: 1 interactive element(s) with zero size
- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=1 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
