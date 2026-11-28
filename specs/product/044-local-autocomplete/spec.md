# 044 Local Autocomplete — Spec

Status: queued (2026-11-28).

## What / Why

The start and destination fields currently search the whole world. For a
walking app the useful answers are around the walker: the country from the
current geolocation, and — where the provider gives it — the city's own
boundary. A worldwide list makes the first suggestions irrelevant, spends
provider quota on places the walk cannot reach, and makes a country/city
mismatch look like a routing failure.

## Scenario

I allow location access. The app resolves my country and city. When I type in
either endpoint field, suggestions are restricted to my city's bounding box;
if the provider has no city box, to my country and a city-scale radius around
me. A clearly labelled fallback keeps the field usable when location is denied
or the context lookup fails. Typed routes and map picks still work unchanged.

## Scope

- `app/geocoding.py` — a `PlaceContext` (country code/name, city, bbox, source)
  from the reverse provider; forward search accepts `country`/`bbox`; Mapbox
  passes `country`/`bbox`, Photon passes `bbox` and filters by country code.
- `app/main.py` — `GET /geocode/context?lat&lng`; `/geocode` accepts optional
  `country` and `bbox`.
- `frontend/src/lib/search/suggestions.ts`, `SearchInput.svelte`,
  `TopSearchCard.svelte`, `App.svelte` — fetch the context after geolocation,
  pass it to both fields, and show a compact "Searching in <city>" hint.
- Tests: context parsing (Mapbox/Photon), provider params/filtering, endpoint
  validation, fetcher URL, and a fixture e2e that types a destination and sees
  only local suggestions.

## Non-goals

- A worldwide search escape ("search anywhere") in this task; the fallback is
  country/radius when the city box is unavailable, and unrestricted only when
  location is denied or the context call fails.
- New geocoding providers or a paid plan change.
- Changing routing, comfort scoring or the map-pick builder.

## Acceptance Criteria

- [ ] AC-1: **Context.** After a successful geolocation the app fetches
  `/geocode/context` and records the country code/name, city and bbox (or a
  city-scale radius fallback). A denied/failed lookup leaves search
  unrestricted and does not error.
- [ ] AC-2: **Restricted suggestions.** Both endpoint fields send `country` and
  `bbox` when the context is known; Mapbox receives `country`/`bbox`, Photon
  receives a bbox and drops results outside the country. A query with no local
  match returns an empty list, not worldwide noise.
- [ ] AC-3: **Exact city box when available.** A reverse `place` result with a
  bbox is used directly; otherwise the country + radius fallback is recorded as
  `source=radius`. The chosen restriction is visible in the endpoint response
  and the UI hint.
- [ ] AC-4: **No regressions.** Typed endpoints, map picks, the 042 builder,
  the 041 frames and the saved-routes capability behave as before; fixtures
  still make the e2e hermetic.
- [ ] AC-5: **Verification.** Unit tests for context/params/filter/URL, the
  full gates, `make e2e`, and the strict acceptance for 001–043 are green.

## Verification

`pytest` for the geocoding/context tests, the frontend unit tests for the
fetcher, the fixture e2e for a local suggestion, and the strict acceptance pass.
The live lane checks that a real reverse lookup returns a country/city for the
042 coordinates.
