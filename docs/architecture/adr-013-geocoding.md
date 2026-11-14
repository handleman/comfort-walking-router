# ADR-013: Geocoding — Mapbox Geocoding v6 → Photon Chain, Normalized `Suggestion`, SQLite TTL Cache

## Context

Spec `014-walk-guidance-ux` (AC-8, AC-9) adds address search and reverse
geocoding to the walking app. Two external providers can serve it:

- **Mapbox Geocoding v6** — high-quality worldwide forward/reverse geocoding,
  but requires a token (`MAPBOX_TOKEN`, the repo-wide variable name, see
  `app/config.py` and ADR-006 for secrets handling).
- **Photon** (photon.komoot.io) — free, tokenless, built on OpenStreetMap
  data; lower match quality and rate limits, but zero setup.

The app must work out of the box with no credentials, yet use the better
provider when one is configured. Provider payloads differ substantially
(Mapbox nests coordinates under `properties.coordinates.{latitude,longitude}`
and returns `full_address`/`feature_type`; Photon uses GeoJSON
`geometry.coordinates` `[lng, lat]` and `properties.name`/`osm_id`), so raw
provider shapes must not leak past the geocoding module into the HTTP layer,
the JSON contract, or the frontend.

Both providers are remote HTTP calls; repeated identical queries (typing in a
search box, re-reversing the same point) would be slow and rate-limited.

## Decision

1. **Provider chain: Mapbox → Photon, chosen per call.** Mapbox Geocoding v6
   is used when `MAPBOX_TOKEN` is set and non-empty; Photon is used otherwise.
   The choice is made per call (not at import time) so tests can switch
   providers by changing the environment. Forward search hits
   `https://api.mapbox.com/search/geocode/v6/forward` or
   `https://photon.komoot.io/api`; reverse geocoding is exposed to clients as
   **`GET /geocode/reverse`** (with `GET /geocode` for forward search) and hits
   Mapbox v6 `/reverse` or Photon `/api/reverse` underneath. Both providers are
   called with `requests` and an 8-second timeout; any transport or parse
   failure degrades to an empty suggestion list, never a 500. The token is
   never logged and never appears in an error message.

2. **One normalized shape: `Suggestion`.** Every provider result is normalized
   in `app/geocoding.py` into a single frozen dataclass, the single source of
   truth for AC-8:

   ```python
   @dataclass(frozen=True)
   class Suggestion:
       id: str          # provider id, e.g. Mapbox id or "osm_type/osm_id"
       label: str       # human-readable single-line address
       lat: float
       lng: float
       type: str        # feature type, e.g. "address", "street", "city"
       attribution: str # required credit string, see README
   ```

   The endpoints return `{"suggestions": [Suggestion, ...]}`; no provider
   payload field appears anywhere else. Malformed features (missing
   coordinates or label) are dropped during normalization.

3. **Attribution travels with every suggestion.** Mapbox results carry
   `© Mapbox © OpenStreetMap`, Photon results
   `© OpenStreetMap contributors` (the provider's own attribution string is
   preferred when present). The frontend renders this credit with results, and
   README documents the setup and credit obligations.

4. **5-minute SQLite cache with TTL.** Geocode responses are cached in SQLite
   (`app/geocode_cache.py`, table `geocode_cache`, database overridable via
   `GEOCODE_CACHE_DB`, in-memory by default) with
   `TTL_SECONDS = 300` — 5 minutes. Cache keys are
   `fwd:{q}:{lat}:{lng}:{limit}` and `rev:{lat}:{lng}`; rows store the JSON
   payload and an `expires_at` timestamp, are upserted on write, deleted lazily
   on expired read, and served before any provider call. The connection is
   shared across threads (FastAPI runs sync endpoints in a threadpool) behind
   a reentrant lock. Cache hits are transparent to callers: the response shape
   is identical either way.

5. **ADR-012 remains the orchestration stance.** This ADR covers only the
   geocoding provider chain, normalization, and caching. It changes nothing
   about the CrewAI Flow control plane, crash-recovery model, or the durable
   orchestrator option recorded in ADR-012.

## Consequences

- Zero-configuration installs work (Photon); adding `MAPBOX_TOKEN` upgrades
  quality with no code change.
- Provider differences are contained in `app/geocoding.py`; the contract,
  frontend, and tests all see only `Suggestion`.
- Suggestions can be up to 5 minutes stale after a provider data change —
  acceptable for address search; the TTL bounds it.
- The cache is best-effort: any SQLite error silently falls through to the
  provider, so caching can never break geocoding.
