# ADR-007: Postgres Switch for Saved Data (005)

## Context
ADR-004 planned SQLite-first with Postgres later behind a repository interface. 005 (no-auth saved routes + prefs) triggers the switch. See `specs/005-saved-routes/spec.md`.

## Decision
- Postgres for `holders` + `routes` + `prefs` via the existing repository interface; SQLite keeps serving only the ephemeral OSM/weather cache.
- Pseudo-auth: server-minted random 128-bit opaque bearer tokens (stored hashed, `holders.token_hash`); first-run bootstrap; per-holder scoping enforced at the repo layer, not just the API.
- TTL: `routes.last_accessed_at` + 90 days expiry via sweep; prefs live with the holder.
- Migrations versioned with downgrade; app boots migrated on fresh install.
- No full accounts by design; multi-user/sharing needs a new ADR.

## Alternatives Considered
- SQLite for everything: zero new infra — rejected (concurrent web writes + durability for user data favor Postgres).
- True accounts now: future-proof — rejected (no requirement; token progress-tracking suffices).
- URL/routable share tokens: shareable links — rejected (leak via history/referrers; bearer-in-storage instead).

## Consequences
- Local dev + CI need Postgres (service/container); cache tests stay SQLite-only.
- Any future multi-user work must revisit identity in a new ADR.
