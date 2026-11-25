# 040-google-maps-layout — Acceptance

Generated: 2026-11-25T22:38:15Z · Verdict: **FAIL** (1 failed · 7 passed · 0 unverified)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | PASS | probe | found 1 element(s); found 1 element(s); count 24 >= 1 |
| AC-2 | PASS | probe | found 1 element(s); found 1 element(s); found 1 element(s); found 1 element(s); absent |
| AC-3 | PASS | probe | found 1 element(s); absent |
| AC-4 | PASS | probe | count 0 vs expect 0; count 0 vs expect 0 |
| AC-5 | PASS | probe | found 1 element(s) |
| AC-6 | PASS | probe | count 7 >= 3; count 6 >= 3 |
| AC-7 | FAIL | probe | 2 console error(s): Failed to load resource: the server responded with a status of 503 (Service Unavailable) \| Failed to load resource: the server responded with a status of 503 (Service Unavailable); 2 console error(s): Failed to load resource: the server responded with a status of 503 (Service Unavailable) \| Failed to load resource: the server responded with a status of 503 (Service Unavailable) |
| AC-8 | PASS | probe | /route request fired |

## Global checks

- **FAIL** desktop: 1 interactive element(s) with zero size (button.grab-handle svelte-mldotw)
- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=1 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
