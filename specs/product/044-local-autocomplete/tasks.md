# 044 Local Autocomplete — Tasks

- [ ] T1 (AC-1): Add `PlaceContext` and `geocoding.context` (Mapbox place/country
  reverse, Photon extent, radius/country fallback, cached) with unit tests for
  the Mapbox, Photon and fallback paths.
- [ ] T2 (AC-1, AC-3): Add `GET /geocode/context` and optional `country`/`bbox`
  parameters on `/geocode` (validation + cache key); test the endpoint and the
  pass-through.
- [ ] T3 (AC-2): Send `country`/`bbox` to Mapbox and `bbox` to Photon, filter
  Photon results by `countrycode`, and test the outgoing params and filtering;
  a no-local-match query returns [].
- [ ] T4 (AC-1, AC-2): Fetch the context after geolocation, pass it through
  `TopSearchCard`/`SearchInput`/`createSuggestionFetcher`, show the
  "Searching in <city>" hint, and leave search unrestricted on denial/failure;
  add frontend unit tests for the URL and the hint.
- [ ] T5 (AC-4, AC-5): Add the fixture context response and e2e assertion, run
  `pytest`, frontend check/lint/unit, `make e2e` and the strict acceptance for
  001–043; add the live `/geocode/context` check for the 042 coordinates.
