# 010 E2E Playwright — Plan

## Approach
Playwright lives entirely under `frontend/` (already in coder scope): config + specs +
npm scripts, no repo-root footprint. Tests drive the real Svelte app against the real
FastAPI backend; external-world dependence (Nominatim/OSRM/Overpass, browser GPS) is
removed via fixtures, the simulated walk provider, and geolocation overrides — so the
suite is deterministic in CI and needs no live internet. Preconditions: 001 T5 (usable
Svelte app), 007 walk mode (sim provider), backend deterministic under a fixtures flag.
Reference spec AC-1..AC-5.

## Steps
1. Toolchain: add `@playwright/test` + `svelte-check`/`vitest` if missing; `playwright.config.ts`
(chromium-only, `baseURL` env-overridable, `webServer` booting `uvicorn app.main:app` +
`vite preview` with reuse + documented manual-servers fallback); `test:e2e` / `test:e2e:headed`
scripts; `test-results/` + `playwright-report/` gitignored (AC-1, AC-5).
2. Determinism harness: backend fixtures flag (recorded Nominatim/OSRM/Overpass responses) or
stub provider so E2E never hits the live internet; Playwright geolocation override + sim
walk provider for position scenarios (AC-2).
3. Route scenarios: search → map render + distance/time; hot/cloudy toggles flip explanation;
repeat query proves cache path (AC-1..AC-3: search, preferences, cache).
4. Walk-mode scenarios (sim provider): Start → origin marker; ticks advance; forced drift →
warning → tap reroutes and replaces route; arrival banner; Stop ends session (007 AC-1..AC-7
through the UI).
5. Error + responsive scenarios: unknown place message; GPS-denied message + sim fallback;
mobile viewport smoke (AC-2).
6. Verify: full `npm run test:e2e` headless green on clean checkout; failure produces trace +
screenshot (gitignored); `npm run check` + `pytest`/`ruff`/`mypy` still green (AC-1, AC-4, AC-5).

## Risks / Open Questions
- Browser install weight (`playwright install chromium` ~150 MB + OS deps) — documented
prereq step, not silent; CI installs once and caches.
- `webServer` boot flakiness (two servers, port races) — strict ports, reuse-existing in dev,
manual-servers fallback documented; headed mode for local debugging only.
- Live-backend drift (fixtures stale vs real APIs) — fixtures refreshed deliberately, never
auto-updated; one manual live smoke per release outside the suite.
- Depends on 001 (app + contract), 007 (walk-mode sim provider); runs last by directory order.
