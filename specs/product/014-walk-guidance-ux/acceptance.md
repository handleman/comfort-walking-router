# 014-walk-guidance-ux — Acceptance

Generated: 2026-11-26T16:47:23Z · Verdict: **FAIL** (1 failed · 4 passed · 2 unverified · 2 n/a)

| AC | Verdict | Source | Evidence |
| --- | --- | --- | --- |
| AC-1 | UNVERIFIED | none | unclear |
| AC-2 | FAIL | probe | /route request fired; clicked; error: locator.waitFor: Error: strict mode violation: locator('.walk-person-marker') resolved to 2 elements:     1) <div tabindex="0" role="button" class="leaflet-marker-icon walk-person-marker leaflet-zoom-animated leaflet-interactive">…</div> aka getByRole('button', { name: 'Your current position (' }).first()     2) <div tabindex="0" role="button" class="leaflet-marker-icon walk-person-marker leaflet-zoom-animated leaflet-interactive">…</div> aka getByRole('button', { name: 'Your current position (' }).nth(1)  Call log: [2m  - waiting for locator('.walk-person-marker') to be visible[22m ; found 2 element(s) |
| AC-3 | PASS | probe | found 1 element(s); found 1 element(s) |
| AC-4 | PASS | probe | /route request fired |
| AC-5 | PASS | probe | /route request fired |
| AC-6 | UNVERIFIED | none | unclear |
| AC-7 | N/A | declared | arrival needs walking into the radius; the e2e suite drives the fix sequence |
| AC-8 | PASS | probe | "pk." absent |
| AC-9 | N/A | declared | gates/documentation |

## Configuration

- **WARN** no acceptance.toml check or not_applicable entry for AC-1, AC-6

## Global checks

- desktop: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
- mobile: tiles=24 · leaflet=True · duplicateButtons=none · zeroSize=0 · overflow=False · routeRequests=0
