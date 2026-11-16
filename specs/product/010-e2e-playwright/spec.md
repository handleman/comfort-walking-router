# 010 E2E Playwright — Spec (MVP final gate)

## What / Why
Close the MVP with true end-to-end tests: a real browser drives the real frontend against
the real backend and asserts what the walker sees. Unit tests prove functions; only E2E
proves the product. Every MVP user scenario gets at least one E2E path; the suite runs
headless via `npm run test:e2e` and stays green alongside the constitution gates.

## Scope
- In scope:
  - Playwright setup under `frontend/`: `@playwright/test` devDep, `playwright.config.ts`
    (chromium-only for speed, `baseURL` from env, `webServer` booting backend + frontend
    with manual-servers fallback documented), `frontend/e2e/*.spec.ts`.
  - Scenarios (each a real browser path, seeded/deterministic data where external calls
    are involved):
    - Search route: enter start/end → scored route renders on the Leaflet map with distance/time.
    - Preferences: hot toggle prefers shade/greenery, cloudy toggle prefers sun; explanation panel lists applied factors.
    - Cache: repeat identical query → second render without backend recompute (observable via API log/indicator, no second external call).
    - Walk mode (simulated provider): Start → marker at origin; ticks advance marker; sustained drift shows "Off route — reroute?" warning; tap requeries and replaces route; arrival shows banner; Stop ends session.
    - Errors: unknown place → clear message, no crash; GPS denied → message + simulated fallback offered.
    - Responsive smoke: mobile viewport (390px) — inputs usable, map renders, no horizontal overflow.
  - Test isolation: each spec resets app state (fresh context or Start-over); no test depends on another's run order.
  - `test-results/` (traces/screenshots on failure) gitignored, never committed.
- Non-goals:
  - No cross-browser matrix (chromium only; Firefox/WebKit are follow-ups, not this spec).
  - No load/performance testing, no real-GPS field tests (sim provider covers walk mode in CI).
  - No visual-snapshot testing (flaky by nature; assert DOM/text/map-layer presence instead).
  - No live external calls in CI: backend calls to Nominatim/OSRM/Overpass run against recorded fixtures or a stubbed provider flag, never the live internet.

## Acceptance Criteria
- [ ] AC-1: `npm run test:e2e` runs the whole suite headless green on a clean checkout (after `npm ci` + `playwright install chromium`).
- [ ] AC-2: Every scenario above has at least one test; all tests independent and order-free.
- [ ] AC-3: Suite proves the walker-visible outcomes (map layer, explanation text, banner, warning), not implementation internals (no selectors on minified class names).
- [ ] AC-4: Failure artifacts (trace + screenshot) are produced on failure and gitignored.
- [ ] AC-5: `pytest` + `ruff check .` + `mypy .` + `npm run check` stay green (E2E adds no backend debt; TS specs type-check).
