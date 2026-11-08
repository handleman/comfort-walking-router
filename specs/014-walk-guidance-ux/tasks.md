# 014 Walk Guidance UX — Tasks

Queue order places 007 before 014; T9 requires 007's `frontend/src/lib/navigation/` modules. Start explicitly with `./swarm/run.sh 014 T1` if needed.

- [ ] T1 (AC-8): Add `app/geocoding.py` with `search(q, lat, lng, limit)` and `reverse(lat, lng)` using Mapbox Geocoding v6 when `MAPBOX_TOKEN` is set and Photon otherwise, normalized `Suggestion` results + attribution; add fixture-only `tests/test_geocoding.py` (no live calls).
- [ ] T2 (AC-4, AC-8): Add `GET /geocode` and `GET /geocode/reverse` in `app/main.py`, `contracts/geocode.json`, 2–120 char/limit/range validation and a 5-minute SQLite cache; extend `tests/test_route_api.py` (or new `tests/test_geocode_api.py`).
- [ ] T3 (AC-5): Add optional `start_coords`/`end_coords` to `RouteRequest` and `contracts/route.json`; use them instead of re-geocoding in `POST /route`, include rounded coords in the cache key, and extend `tests/test_route_api.py`.
- [ ] T4 (AC-1, AC-2): Add `frontend/src/lib/map/icons.ts` (Bootstrap Icons `person-walking` MIT inline SVG; blue start/red end pins; accessible labels) and `frontend/src/lib/geo/current.ts` (position state machine), each with a vitest `*.test.ts`.
- [ ] T5 (AC-1): Wire on-mount `map.locate({setView, maxZoom:16, timeout:8000, enableHighAccuracy:true})`, the green current-position glyph, and a denial/timeout notice with "Use my location" retry in `frontend/src/App.svelte`.
- [ ] T6 (AC-3): Add pick buttons right of Start/End plus `frontend/src/lib/map/picker.ts` in `frontend/src/App.svelte`: crosshair mode, one active role, map click → `GET /geocode/reverse` label → input + blue/red glyph replacement, `Esc` cancel, no form submit.
- [ ] T7 (AC-4): Add `frontend/src/lib/components/SearchInput.svelte` and `frontend/src/lib/search/suggestions.ts` (280 ms debounce, min 2 chars, AbortController, stale-request guard, ARIA combobox/listbox, ↑/↓/Enter/Esc + mouse/touch), with vitest coverage.
- [ ] T8 (AC-4, AC-5): Wire selection and map picks in `frontend/src/App.svelte` to `start_coords`/`end_coords`, clear pinned coords on input edit, and render blue/red glyphs from `route.waypoints` after a successful route (replace previous markers).
- [ ] T9 (AC-6, AC-7): Reuse 007's `frontend/src/lib/navigation/` snap/interpolate/drift/arrival modules; use `personIcon()` as the walk marker and add `frontend/src/lib/components/ArrivalCard.svelte` (distance/duration/comfort/top factors, dismiss + plan another) on the 25 m arrival signal.
- [ ] T10 (AC-8, AC-9): Add attribution display, cache/TTL and ADR-012 (`docs/architecture/adr-012-geocoding.md`), update `README.md`/`docs/roadmap.md`/`docs/tech-stack.md`, add `frontend/e2e/walk-guidance.spec.ts` to the 010 suite with mocked `/geocode` + geolocation, and run `make test`/`make lint`/`make typecheck`/`npm run check`/`npm test`.

<!-- Human gate, not queued: verify a real GPS permission prompt + one manual map-pick/autocomplete
     flow in a browser over localhost/HTTPS, then mark AC-1..AC-9 and tick 014. -->
