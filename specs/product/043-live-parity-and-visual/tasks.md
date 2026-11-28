# 043 Live Parity and Visual Honesty — Tasks

- [ ] T1 (AC-1): Add `GET /capabilities` (`saved_routes`/`database` from
  `DATABASE_URL`, no DB access) and hide the mobile Saved button, the save-route
  control and the nav Saved-walks entry when it is false; add a pytest and an
  e2e assertion. Keep the 503 API response and the configured-DB flow.
- [ ] T2 (AC-2): Add the missing builder CSS to `BottomDrawer.svelte` (52 px
  brand pill, destination/error slots, 041 tokens), verify the Edit row opens
  the styled PreferencesSheet, and add a computed-style/unit or e2e assertion
  for the pill background/height/radius.
- [x] T3 (AC-3): Bound the corridor lookup (total 8 s, parallel mirrors or one
  fast endpoint, QL timeout under the budget) and return a weather-only 200
  when it misses; keep a typed provider error. Add a slow-Overpass test with a
  <10 s assertion and an honest `comfort_data` gap in the payload.
- [x] T4 (AC-4): With the route held, assert the builder closes and
  `[data-testid="route-loading"]` is visible/on top; on success it dissolves and
  the route is drawn; on 500 the builder reopens with the error. Add the mobile
  screenshot used by the visual gate.
- [x] T5 (AC-5): Restore `frontend/e2e/build-route.spec.ts` (mobile 390×844,
  fixture reverse geocode, no `/route` before Build, held spinner, success
  dissolve + drawn route, 500 reopen), save the builder and route viewport
  screenshots under `frontend/test-results/`, declare AC-1..7 `covered_by` it,
  add 042 `live.toml` with the 042 coordinates and a <15 s latency check, and
  run `make e2e`, `make swarm-accept --strict` and `make accept-live`.
- [x] T6 (AC-5): Add the 041/042 visual regions (mobile sheet chrome + builder
  CTA, desktop nav/sidebar) for the 062 gate, deploy to Render, run the live
  route twice and capture the 390×844 screenshot; the configured region must be
  >=90% similar.
- [x] T7 (AC-3): Finish T3's bounded-corridor change: `comfort._overpass_features`
  returns `None` on every mirror failure (never live counts or an uncaught
  error); `factors_from_counts` accepts a valid GeoJSON corridor with a
  `highway=footway` way; the aggregate "all endpoints failed" line is emitted;
  an invalid-JSON payload raises `OverpassProviderError` matching "invalid
  JSON". Update `tests/test_overpass_retry.py` from the old `[90,90,90]`
  sequential expectation to the bounded budget. `pytest -q` green.
- [x] T8 (AC-3): Do not rewrite the Overpass provider or its 90 s test.
  Bound the route response at the join: wrap `comfort.corridor_data(geometry)`
  in a short-lived executor with a 10 s deadline in `_build_response`; on
  `TimeoutError`, use `corridor = None` and keep the weather-only score. Add a
  pytest that a sleeping corridor returns in <10 s with `comfort_data is None`.
  `pytest -q` green.
