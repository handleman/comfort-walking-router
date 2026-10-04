# ADR-004: Storage — SQLite Cache First, Postgres Later

## Context
MVP needs cheap repeat-query caching for routing/geodata (OSRM interim, Overpass, Nominatim; Mapbox in 008) responses; saved routes/prefs come later. See `docs/tech-stack.md`, roadmap `005-saved-routes`.

## Decision
- Now: SQLite cache keyed by (start, end, preference) for OSM responses/scores; TTL + cache-hit path that skips externals (001 AC-3).
- Later (`005-saved-routes`): Postgres for saved routes/prefs (+ accounts if needed), behind repository interface so the scorer/cache code does not change shape.
- No ORM lock-in at MVP: stdlib `sqlite3` (or minimal wrapper) with DI-provided connection.

## Alternatives Considered
- Postgres from day one: prod-ready — rejected (setup/ops cost before product signal).
- No cache / in-memory only: simplest — rejected (demo-server rate limits would bite immediately).
- File/HTTP cache (e.g. disk blobs): easy — rejected (queryable keying + TTL cleaner in SQLite).

## Consequences
- Zero-infra MVP with polite external usage; migration to Postgres is a scoped, ADR-backed step.
- Must keep storage access behind an interface (constitution P8) so the swap stays mechanical.
