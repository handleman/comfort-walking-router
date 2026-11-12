# 014 Walk Guidance UX — Plan

Status: proposed. References `specs/014-walk-guidance-ux/spec.md` AC-1–AC-9. Builds on `001` (scored route UI), `007` (walk-mode movement), optional `008` (Mapbox routing). The swarm queue runs 014 after 007/010; explicit `./swarm/run.sh 014 T1` can start it sooner.

## Research (2026-11-08)

### Leaflet
- Native geolocation is `map.locate({watch, setView, maxZoom, timeout, maximumAge, enableHighAccuracy})`; success fires `locationfound`, failure `locationerror`, and `map.stopLocate()` stops a watch. Geolocation is only available on secure contexts.
- Custom markers use `L.divIcon({html, className, iconSize, iconAnchor})`; this lets us inline an SVG and recolor with `currentColor` without image assets or an icon font.

### Icons
- Bootstrap Icons `person-walking` is **MIT**, single-color (`currentColor`), 16×16 path, free for commercial use; redistribution requires keeping the license notice.
- Material Symbols `directions_walk` is **Apache-2.0**, also `currentColor`.
- Decision: **inline Bootstrap Icons SVG** (`person-walking`, MIT) in `frontend/src/lib/map/icons.ts`; no font file, no CDN, no FOUT. Start/end pins are small custom SVG paths (blue/red) with `A`/`B` labels. Keep a license comment in the file.

### Geocoding
- **Mapbox Geocoding v6** (`GET https://api.mapbox.com/search/geocode/v6/forward`):
  `q`, `autocomplete` (default true; every keystroke is a request), `proximity=lon,lat`, `types=address,street,place,locality,neighborhood`, `limit` (max 10), `language`.
  Response: `features[].properties.full_address`, `feature_type`, `coordinates.{latitude,longitude}` and a top-level `attribution` string. Reverse: `/search/geocode/v6/reverse?longitude=&latitude=&types=&language=`; same feature shape.
- **Photon** (`https://photon.komoot.io/api?q=&lat=&lon=&limit=&lang=` and `/reverse?lat=&lon=`): keyless OSM geocoder designed for search-as-you-type, GeoJSON features with `name`, `street`, `housenumber`, `city`, `postcode`, `type`, `geometry.coordinates`; supports `suggest_addresses` for house numbers.
- **Nominatim**: already used by `app/geocoder.py` for final submit. Its usage policy forbids client-side autocomplete/predictive search, so it is **not** used for suggestions; keep it only as the submit fallback.
- Decision: provider order **Mapbox (if `MAPBOX_TOKEN`) → Photon**; normalize to one `Suggestion` shape; keep Nominatim for `POST /route` text fallback. Proxy through the backend so the token never reaches the browser. Cache suggestions for ≤5 minutes and send `permanent=false` (temporary Mapbox results), display attribution.

### Current code (grounding)
- `frontend/src/App.svelte` uses Leaflet directly, a single `start`/`end` string form, `POST /route`, and draws the route + circles from `route.waypoints`. No geolocation, picker, autocomplete, or walk mode.
- `app/main.py` calls `geocode_place()` (Nominatim) for both strings; `contracts/route.json` only accepts strings.
- `007` defines `frontend/src/lib/navigation/{interpolate,snap,drift,arrival}.ts`, providers, auto-center, and the 25 m arrival radius; 014 must reuse, not redefine.

## Design

### Backend
- `app/geocoding.py` — the **provider-normalization layer**. It is the single source of
  truth for the `Suggestion` shape and the provider wire formats; the HTTP layer
  (`app/main.py`) and the contract (`contracts/geocode.json`) are derived from it.
  - `Suggestion` dataclass (flat, one field per value — no nested `coordinates`
    object): `id: str`, `label: str`, `lat: float`, `lng: float`, `type: str`,
    `attribution: str`.
  - `search(q, lat=None, lng=None, limit=5) -> list[Suggestion]` and
    `reverse(lat, lng) -> list[Suggestion]` (a list in both cases, so the two
    call sites share one shape). `attribution` travels on every `Suggestion`
    (AC-8: attribution is displayed with the data it describes).
  - **Provider selection:** Mapbox when `MAPBOX_TOKEN` is set and non-empty
    (the repo-wide variable name — `app/config.py:get_mapbox_token()` reads
    `MAPBOX_TOKEN`; do **not** invent `MAPBOX_ACCESS_TOKEN`), Photon otherwise.
    The provider is decided per call, not at import time, so a test can switch it.
  - **Mapbox (Geocoding v6)** — `GET https://api.mapbox.com/search/geocode/v6/forward`
    with `q`, `access_token`, `proximity=lng,lat` (only when both coordinates are
    known), `types=address,street,place,locality,neighborhood`, `language=en`,
    `autocomplete=true`, `limit` (≤10); reverse uses `/search/geocode/v6/reverse`
    with `longitude`, `latitude`, `types`, `language`, `limit=1`.
    `requests` with an 8 s timeout; the token is never logged.
    Response (v6): `features[]` each with `id`, `properties.full_address`
    (the label), `properties.feature_type` (the type), `properties.coordinates`
    = `{latitude, longitude}` (the position), plus a top-level `attribution`.
  - **Photon** — `GET https://photon.komoot.io/api` with `q`, `lat`, `lon`,
    `limit`, `lang=en`; reverse uses `/api/reverse` with `lat`, `lon`, `limit`,
    `lang=en`.
    Response: GeoJSON `features[]` with `properties.name` (the label),
    `properties.type` (the type), `geometry.coordinates` = `[lng, lat]`, plus a
    top-level `attribution`.
  - Fail soft: a provider error yields `[]` (never an exception); the reverse
    caller falls back to a coordinate label.
- **The wire contract** (`contracts/geocode.json`) mirrors `Suggestion` field for
  field — `{id, label, lat, lng, type, attribution}` — so there is exactly one
  shape in the system. The provider payloads are an implementation detail of
  `app/geocoding.py` and never leak past it.
- `GET /geocode?q=&limit=&lat=&lng=`:
  - validate `q` length 2–120, `limit` 1–10; return `{suggestions, attribution}`
    where every suggestion is a `Suggestion` (the shape above).
  - 5-min SQLite cache key `(provider, normalized_q, rounded lat/lng, limit)`; cache stores normalized results only.
- `GET /geocode/reverse?lat=&lng=`: validate ranges; return `{suggestions, attribution}`
  (fallback: one suggestion whose label is the rounded coordinates).
- `POST /route`: `RouteRequest` gains optional `start_coords: {lat,lng}` / `end_coords`; if present use them, else `geocode_place(text)`. Cache key includes rounded coordinates to avoid collisions. Response unchanged.
- `contracts/geocode.json` (new) and an additive `contracts/route.json` change; `tests/test_geocoding.py` uses recorded fixtures, never the network.

### Frontend
- `frontend/src/lib/map/icons.ts`: `personIcon()`, `startIcon()`, `endIcon()` returning `L.divIcon` HTML; person = white halo + green walking SVG (Bootstrap Icons path; license comment); pins = blue/red SVG with `A`/`B`; `aria-label` via `title`/`alt`.
- `frontend/src/lib/geo/current.ts`: small state machine (`idle → requesting → granted|denied|unsupported|timeout`), `requestCurrentPosition()`, `watchPosition()`/`stopWatch()` wrappers with injected `navigator.geolocation` for tests.
- `frontend/src/lib/map/picker.ts`: `PickerState` (`null | 'start' | 'end'`), `enter(role)`, `cancel()`, `handleClick(latlng)`; one active role; cursor class on the map container.
- `frontend/src/lib/search/suggestions.ts`: `fetchSuggestions()` with `AbortController`, request-id guard, 280 ms debounce, min length 2; it calls `GET /geocode?q=...` (the backend path — the app serves its routes unprefixed, like `/route`) and normalizes the response's `suggestions` array into the component's shape; pure unit tests.
- `frontend/src/lib/components/SearchInput.svelte`: ARIA combobox (`role=combobox`, `aria-expanded`, `aria-activedescendant`, listbox), keyboard/mouse selection, clear-on-edit, error/empty states, attribution line.
- `frontend/src/lib/components/ArrivalCard.svelte`: congratulation card (distance, duration, comfort, top factors), dismiss + "Plan another walk".
- `App.svelte` wiring:
  - on mount: `map.locate({setView:true, maxZoom:16, timeout:8000, enableHighAccuracy:true})`; `locationfound` → person marker + green pulse-free halo; `locationerror` → notice + retry button; fallback center unchanged.
  - `startSel`/`endSel` (`{label,lat,lng}` | null); input edit clears the selection; submit sends coords when present.
  - pick buttons beside the inputs; pick mode sets selection + reverse-geocoded label; `Esc` cancels.
  - route success: remove old markers, draw blue/red pins from `route.waypoints` (replaces previous).
  - walk mode: 007's provider/store; use `personIcon()` as the moving marker; on arrival show `ArrivalCard`, stop tracking, keep the route visible.
- No new npm dependency for icons; 007 adds vitest; if it is not present, the first task that needs tests adds the same minimal vitest setup rather than a second framework.

### State / edge cases
- Editing a selected input clears its pinned coordinates but keeps text; submitting then uses string geocoding.
- A map pick while the other picker is active cancels it; `Esc` restores the form.
- Reverse-geocode failure still sets the point and uses `lat.toFixed(5), lng.toFixed(5)` as the label.
- Geolocation denied: no repeated prompts on every render; only the retry button re-requests.
- Attribution: Mapbox text from the response; Photon → `© OpenStreetMap contributors`; shown under suggestions and in the map attribution control.
- Cache: suggestions ≤5 min, never written to long-term storage; no token in cache keys/logs.

## Files
- `app/geocoding.py` (new), `app/main.py`, `contracts/geocode.json` (new), `contracts/route.json`, `tests/test_geocoding.py`, `tests/test_route_api.py`.
- `frontend/src/lib/map/icons.ts`, `frontend/src/lib/geo/current.ts`, `frontend/src/lib/map/picker.ts`, `frontend/src/lib/search/suggestions.ts`, `frontend/src/lib/components/SearchInput.svelte`, `frontend/src/lib/components/ArrivalCard.svelte`, `frontend/src/App.svelte`.
- `frontend/src/lib/**/*.test.ts` (vitest), `frontend/e2e/walk-guidance.spec.ts` (010 extension).
- `docs/architecture/adr-012-geocoding.md` (new), `README.md`, `docs/roadmap.md`, `docs/tech-stack.md`.

## Delivery steps
1. Backend provider + normalization + fixtures.
2. Endpoints, validation, cache, contracts.
3. Additive route coordinates + tests.
4. Icon module + geolocation state machine.
5. App load-time geolocation + fallback + current glyph.
6. Pick buttons/mode + reverse geocode + glyph replacement.
7. Combobox component + debounce/abort + keyboard/mouse.
8. Selection→coords→submit→waypoint glyphs; edit invalidation.
9. Walk marker uses the person glyph; arrival congratulation card (blocked by 007).
10. Attribution/cache/ADR/docs, extend 010 E2E, full gates.

## Risks / open questions (resolved choices)
- **007 not done when 014 runs:** tasks T9 depend on it; the queue order already puts 007 first. If 007 is still open, stop 014 at T8 and leave T9 blocked.
- **Mapbox attribution/storage:** use temporary results, 5-minute cache, display `attribution`; no `permanent=true`.
- **Photon/Nominatim policy:** Photon for type-ahead, Nominatim only after submit; identifier/UA on every request.
- **Token leakage:** backend proxy only; never log or echo the token; tests use a fake token and fixtures.
- **Permission UX:** request once on load, then only via the retry button; no repeated prompts.
- **Svelte reactivity:** keep map objects outside reactive state; clear listeners/markers in `onDestroy`.
- **Duplication with 007/010:** 014 consumes 007's modules and adds one 010 scenario; it must not reimplement snap/drift/arrival.
