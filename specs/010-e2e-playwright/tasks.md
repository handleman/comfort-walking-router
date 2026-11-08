# 010 E2E Playwright — Tasks

- [ ] T1 (AC-1, AC-5): Add `@playwright/test` + `playwright.config.ts` under `frontend/` (chromium-only, `baseURL` from env, `webServer` booting backend + frontend, `test:e2e`/`test:e2e:headed` scripts), run `npm install` there to update the lockfile, and gitignore `test-results/` + `playwright-report/`.
- [ ] T2 (AC-2): Add a `ROUTE_FIXTURES=1` backend mode in `app/fixtures.py` wired from `app/main.py` (recorded Nominatim/OSRM/Mapbox/Overpass responses, no live internet) with `tests/test_fixtures_mode.py`.
- [ ] T3 (AC-2, AC-3): Add `frontend/e2e/helpers.ts` (fresh context, fixtures env, geolocation/sim overrides) and the search scenario `frontend/e2e/search.spec.ts` (enter start/end → scored route renders on the map with distance/time).
- [ ] T4 (AC-2, AC-3): Add preference + cache scenarios in `frontend/e2e/preferences.spec.ts` (hot/cloudy flip the explanation factors; repeat identical query renders without a second external call).
- [ ] T5 (AC-2, AC-3): Add the walk-mode scenario in `frontend/e2e/walk-mode.spec.ts` via the sim provider (Start → origin marker → ticks → drift warning → tap reroutes → arrival banner → Stop).
- [ ] T6 (AC-2, AC-3): Add error + responsive scenarios in `frontend/e2e/errors-responsive.spec.ts` (unknown place message; GPS denied message + sim fallback offered; 390px viewport with usable inputs, rendered map, no horizontal overflow).

<!-- Human/CI gate, not queued (no code change): `npx playwright install chromium` on the machine
     or CI image, then run `npm run test:e2e` headless on a clean checkout and confirm failure
     traces/screenshots are produced but gitignored. -->
