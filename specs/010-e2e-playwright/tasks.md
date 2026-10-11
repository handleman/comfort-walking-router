# 010 E2E Playwright — Tasks

- [ ] T1 (AC-1, AC-5): Playwright toolchain under `frontend/` (`@playwright/test`, `playwright.config.ts` chromium-only + `webServer`, `test:e2e`/`test:e2e:headed` scripts, gitignore test artifacts).
- [ ] T2 (AC-2): Determinism harness (backend fixtures flag/stub provider, geolocation override, sim walk provider wiring) — no live internet in CI.
- [ ] T3 (AC-2, AC-3): Route scenarios (search → render + distance/time; hot/cloudy flips; repeat-query cache path) asserting walker-visible outcomes.
- [ ] T4 (AC-2): Walk-mode scenarios via sim provider (Start → marker; ticks; drift → warning → tap reroute; arrival banner; Stop).
- [ ] T5 (AC-2): Error scenarios (unknown place message; GPS-denied message + sim fallback) + mobile viewport smoke.
- [ ] T6 (AC-1, AC-4, AC-5): Full headless green on clean checkout; failure trace+screenshot verified gitignored; `npm run check` + `pytest`/`ruff`/`mypy` still green.
