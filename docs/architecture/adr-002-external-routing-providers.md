# ADR-002: External Routing + Geodata Providers (MVP)

## Context
MVP needs walking geometry, comfort features (shade/greenery, traffic), and place-name geocoding with no self-hosted infra and no API keys. Mapbox (free tier) is the planned post-MVP provider (`008-mapbox-routing`). See `specs/001-example-app/plan.md` (Nominatim → OSRM interim → Overpass → scorer → SQLite cache).

## Decision
- MVP base routes: OSRM public demo server (`router.project-osrm.org`), foot profile, 1–2 alternatives, short timeout + single retry — behind a provider interface so 008 swaps it mechanically.
- Post-MVP (`008`): Mapbox Directions API (walking, free tier), token server-side only via env var (`MAPBOX_TOKEN`), never exposed to frontend.
- Comfort features: Overpass API over OSM tags (parks/trees/paths/roads); debounced, cached.
- Geocoding: Nominatim (usage-policy compliant: single req, caching, OSM attribution in UI).
- Mitigation: SQLite cache keyed by (start, end, preference); cache-hit skips all externals.

## Alternatives Considered
- Mapbox in MVP: reliable SLA — deferred to 008 (keep MVP keyless, prove loop first).
- Self-hosted Valhalla/OSRM: rejected outright (no self-hosting, per product decision).
- Google routing API: reliable — rejected (cost vs Mapbox free tier).
- Mocked geometry: fastest tests — kept only as test fixture, not prod path.

## Consequences
- Keyless MVP; OSRM demo rate limits/downtime possible — cache + timeouts bound the blast radius.
- 008 swaps the provider behind the scorer interface (constitution P8); Mapbox quota then mitigated by the same cache + debounce. No self-hosting ever planned.
