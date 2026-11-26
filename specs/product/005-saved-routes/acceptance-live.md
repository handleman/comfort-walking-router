# 005-saved-routes — Live acceptance

Generated: 2026-11-26T16:21:01Z · Target: local stand, real providers (fixtures off) · Database: used

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1 | FAIL | live_route: 1485 m / 1029 s; click: clicked; wait_for: error: locator.waitFor: Timeout 10000ms exceeded.
Call log:
[2m  - waiting for locator('section.saved-routes:visible .saved-list li') to be visible[22m
; exists: not found; click: error: locator.click: Timeout 30000ms exceeded.
Call log:
[2m  - waiting for locator('section.saved-routes:visible button:has-text(\'Recall\')')[22m
; text: text "Route summary Auto: cloudy -0.6°C Marienplatz, 80331 Munich, Germany → Englischer Garten Süd, Munich" missing "Marienplatz, Munich"; click: error: locator.click: Timeout 30000ms exceeded.
Call log:
 |
