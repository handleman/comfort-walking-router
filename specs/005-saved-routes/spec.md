# 005 Saved Routes — Spec

## What / Why
Persist scored routes and prefs in Postgres for recall and reuse. No accounts — instead a server-issued opaque bearer token tracks each walker's progress. Simplest durable step per ADR-004, with proportionate security.

## Scope
- In scope:
  - Postgres behind the repository interface (ADR-004); migration creating `holders` (token hash + created_at), `routes` (holder FK + request + response snapshot + created_at + last_accessed_at), `prefs` (one row per holder: default preference).
  - Identity: first run mints a random 128-bit opaque token (returned once, stored in browser localStorage, sent as `Authorization: Bearer`); every query scoped by holder; tokens stored as hashes, never in URLs or logs.
  - API: save current route, list, recall by id (refreshes `last_accessed_at`), delete; get/update prefs — all token-scoped (wrong-holder id → 404).
  - TTL: routes expire 90 days after last access (sweep job/cascade); prefs persist while holder exists.
  - Svelte: save button, saved list, recall, prefs editor (default hot/cloudy); first-run token bootstrap invisible to the walker.
  - Security baseline (learning-repo proportionate): unguessable tokens, per-holder scoping enforced at repo layer, no token leakage (logs/URLs/errors), HTTPS assumed in prod note.
- Non-goals:
  - No accounts, no sharing, no cross-device sync (token lives in one browser).
  - No migration of SQLite cache contents (cache stays ephemeral).

## Acceptance Criteria
- [ ] AC-1: Save route → appears in list; recall reproduces the scored route identically; delete removes it (all token-scoped).
- [ ] AC-2: Prefs (default preference) survive backend restart.
- [ ] AC-3: Fresh install migrates cleanly; migration downgrade restores prior schema.
- [ ] AC-4: SQLite cache behavior unchanged (001 AC-3 still green).
- [ ] AC-5: `pytest` + `ruff check .` + `mypy .` + `npm run check` clean; repo layer unit-tested with transactional fixtures.
- [ ] AC-6: Cross-holder access impossible — recalling another holder's route id returns 404; no token in logs/URLs.
- [ ] AC-7: Routes untouched for 90 days expire (sweep); prefs persist; recall refreshes `last_accessed_at`.
