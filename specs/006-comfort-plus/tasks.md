# 006 Comfort-Plus — Tasks

- [ ] T1 (AC-1, AC-2, AC-3): Extend the corridor lookup in `app/providers/overpass.py` for `lit` + `highway` tags with fixtures in `tests/fixtures/overpass-*.json` and tests in `tests/test_overpass_tags.py`.
- [ ] T2 (AC-2, AC-3): Add `prefer_lit` + `avoid_traffic` factors to `app/scoring.py` (equal weights, honest data-gap notes) with matrix tests in `tests/test_scoring_plus.py`.
- [ ] T3 (AC-1): Add `prefer_lit`/`avoid_traffic` to `contracts/route.json` `RouteRequest` and pass them through `app/main.py` with API tests in `tests/test_route_toggles.py`.
- [ ] T4 (AC-1, AC-2): Add the two toggles + per-factor explanation to `frontend/src/App.svelte`; keep `npm run check` green.
- [ ] T5 (AC-4, AC-5): Add the 001 regression matrix (shade/sun/quiet, cache, contract) in `tests/test_scoring_regression.py` and keep the full gates green.
