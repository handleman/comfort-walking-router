# 014 Walk Guidance UX — Spec

**Status: proposed** (2026-11-08). Depends on `001-T10` (frontend score panel) and `007-live-position` (walk mode); optional `008-mapbox-routing`.

## What / Why
The MVP route screen still assumes the walker types two free-text places and looks at a static map. Browser testing surfaced seven concrete gaps:

1. The map does not use the walker's position by default and has no "you are here" marker.
2. There is no walking-person glyph; start/end points are anonymous circles.
3. Start/end cannot be picked on the map; there is no crosshair/pick mode and no blue/red destination glyphs.
4. While walking, there is no person marker moving along the route (007 defines the movement rules; the UI still needs to show it).
5. Reaching the destination has no congratulation/arrival moment.
6. A Mapbox token is available in `.env` but must stay backend-only.
7. Start/end inputs have no address/street/building autocomplete, and selecting a suggestion does not pin the exact coordinates or place a glyph.

This spec defines the **walk-guidance UX layer**: geolocation onboarding, map-picked points, address autocomplete, person/start/end glyphs, and the arrival moment. Movement/snap/drift rules stay owned by 007; this spec consumes them.

## Scope
- In scope:
  - `app/geocoding.py` (new) + `GET /geocode` / `GET /geocode/reverse` in `app/main.py`: Mapbox Geocoding v6 (backend token) with Photon fallback; normalized suggestions with attribution.
  - Additive `POST /route` request fields `start_coords` / `end_coords` so a selected/picked point is exact; response contract unchanged.
  - `contracts/geocode.json` + additive `contracts/route.json` update.
  - `frontend/src/App.svelte` + new `frontend/src/lib/` modules/components: geolocation state, SVG map icons, map-pick mode, combobox search input, arrival card, walk-marker wiring.
  - Backend pytest + frontend TS/vitest tests; one Playwright scenario extension for 010.
  - Docs: `swarm` not involved; `README.md`/roadmap/spec table + ADR-012 (geocoding provider/token boundary).
- Non-goals:
  - No change to 007's snap/drift/arrival thresholds or auto-center rules.
  - No Mapbox Directions swap (008), no routing-provider change.
  - No voiceover, turn-by-turn, background tracking, offline/PWA, saved routes (005), or i18n.
  - No geofencing/push notifications; no live external calls in tests.
  - No cross-browser matrix (010 owns E2E breadth).

## Acceptance Criteria
- [ ] AC-1: **Geolocation on load.** On mount the app requests the browser position (timeout ≤8 s). Success centers the map on the user (≤ zoom 16) and shows the current-position glyph. Denial/timeout/unsupported keeps a usable fallback center, shows a non-blocking notice and a "Use my location" retry; no blocking error or repeated permission prompts.
- [ ] AC-2: **Person glyph.** The current-position/walk marker is a green walking-person, rendered as an inline SVG `L.divIcon` (Bootstrap Icons `person-walking`, MIT) on a high-contrast halo, ~32–36 px, with an accessible label; no external font/CDN request. Start/end are blue/red pin glyphs (blue start, red end), one per role, replaced when the point changes.
- [ ] AC-3: **Map pick.** Start and End each have a button to their right. Clicking enters pick mode (crosshair cursor, instruction), a map click sets that point, reverse-geocodes a label into the input, places/replaces that role's glyph, and exits pick mode. `Esc` cancels; starting the other picker cancels the first; clicking the map never submits the form. Touch works.
- [ ] AC-4: **Autocomplete.** Inputs behave as ARIA comboboxes: ≥2 characters, ~250–300 ms debounce, at most 5 suggestions, stale responses ignored, loading/empty/error states non-blocking. Keyboard `↑`/`↓`/`Enter`/`Esc` and mouse/touch selection work. `Enter` selects the highlighted suggestion; with no list open, `Enter` submits the form. A selection fills the input and pins its exact coordinates; editing the text invalidates the pinned point until a new selection.
- [ ] AC-5: **Exact submission.** When a point came from a suggestion or map pick, `POST /route` receives optional `start_coords`/`end_coords` and the backend uses them instead of re-geocoding; typed-only text still works exactly as before. The response shape is unchanged and route waypoints match the selected points. Route success renders blue/red glyphs from `route.waypoints`, replacing any previous markers.
- [ ] AC-6: **Moving person.** In walk mode the green person marker moves along the route using 007's `interpolate`/`snap`/`drift` modules and thresholds (no jitter, no auto-reroute); auto-center stays 007's behaviour; Stop removes the marker.
- [ ] AC-7: **Arrival moment.** Crossing 007's 25 m arrival radius shows a one-time congratulation card ("You made it") with distance, duration, comfort score and top factors; tracking stops; the card is dismissible and offers "Plan another walk"; `role="status"`, no focus trap.
- [ ] AC-8: **Provider discipline.** `MAPBOX_TOKEN` is backend-only (never in the frontend bundle or requests); Mapbox is used when configured, Photon otherwise, Nominatim only for final submit geocoding. Suggestions are debounced and briefly cached (≤5 min, `permanent=false`), never permanently stored; Mapbox/OSM attribution is displayed when their data is used.
- [ ] AC-9: **Gates.** Backend `pytest`, `ruff check .`, `mypy app tests`; frontend `npm run check` + vitest unit tests; no live Mapbox/Photon/Nominatim calls in tests; one 010 E2E scenario covers select→route→glyphs (mocked `/geocode` + geolocation permission). All existing route/007 tests stay green.

## Dependencies / Risks
- **007 must land first** for AC-6/AC-7; if it has not, those tasks are blocked and the rest (AC-1–AC-5) still ships.
- Mapbox terms require attribution and restrict permanent storage; we use temporary results, short cache, and display the returned attribution.
- Browser geolocation requires a secure context (`https://` or `localhost`); document how to run Vite locally.
- Photon is a best-effort public service; failures fall back to Nominatim for submit (never autocomplete) and surface a non-blocking error.
- 001-T10 will change `App.svelte`; tasks assume its scored-result panel exists and only add to it.
