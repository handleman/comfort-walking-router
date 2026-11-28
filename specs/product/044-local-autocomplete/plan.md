# 044 Local Autocomplete — Plan

1. **Context type.** Add `PlaceContext(country_code, country, city, bbox,
   source)` and `geocoding.context(lat, lng)`:
   - Mapbox: reverse `types=locality` (or `place`, `region`, `country`) for the
     country context and city name; a `place` reverse with a bbox is used
     directly, otherwise one cached forward `types=place` lookup resolves the
     city bbox (Minsk reverse returns the district, not the place).
   - Photon: reverse `limit=5`, pick the city/place feature's `countrycode`,
     name and `extent`; parse the extent into `(west,south,east,north)`.
   - No provider or no city box → a ±0.25° radius around the point,
     `source="radius"`; no country → unrestricted.
   - Cache by rounded coordinates.
2. **Endpoint.** `GET /geocode/context?lat&lng` returns
   `{country, country_code, city, bbox, source}` (empty when the provider has
   nothing). `/geocode` adds optional `country` (ISO alpha-2, 2 chars) and
   `bbox` (`west,south,east,north`, validated order) and passes them through;
   include them in the cache key.
3. **Providers.** Mapbox forward sends `country` and `bbox` (plus the existing
   proximity). Photon forward sends `bbox` (minLon,minLat,maxLon,maxLat) and
   post-filters features whose `countrycode` differs. Keep the 8 s timeout and
   fail-soft empty list.
4. **Frontend.** `App.svelte` fetches `/geocode/context` when geolocation
   succeeds (and on a "my location" start), stores it, and passes
   `country`/`bbox`/`city` to `TopSearchCard`. `SearchInput` passes them to
   `createSuggestionFetcher`, which appends the query parameters. Render a
   small hint under the active field: "Searching in <city>" (or "in <country>"
   for the radius fallback). On denial/failure, no hint and no restriction.
5. **Fixtures/tests.** Fixtures keep returning the recorded suggestion; add
   unit tests that the URL/params carry the context and that the backend filters
   Photon results by country. Add an e2e fixture context response and assert the
   hint plus a local suggestion.
6. **Verify.** `pytest`, frontend unit/check/lint, `make e2e`, strict
   acceptance; the live lane calls `/geocode/context` for the 042 coordinates
   and records the country/city/source.

## Risks

- Mapbox v6 bbox/country parameter names are easy to get wrong; a fixture
  asserts the outgoing params, and a live call in the lane catches a 4xx.
- A city box can be large or missing; the radius fallback keeps the field
  usable. An empty result is better than a worldwide list, but the UI should not
  look broken — show the hint and a quiet "no local matches".
- Denied location must not block typing; unrestricted is the deliberate
  fallback, not an error.
- The context call is one extra reverse request per location; cache it and do
  not call it on every keystroke.
