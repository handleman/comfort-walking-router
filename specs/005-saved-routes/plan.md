# 005 Saved Routes — Plan

## Approach
Storage slice per ADR-004/ADR-007: Postgres repo + migrations behind the existing interface, opaque-bearer pseudo-auth, 90-day route TTL, thin API, minimal Svelte save/recall UI. Reference spec AC-1..AC-7.

## Steps
1. Repo + migrations: `holders` / `routes` / `prefs` tables, up/down, Postgres service for dev/CI (AC-3, AC-5).
2. Identity: token mint (128-bit, hashed storage) + first-run bootstrap + repo-layer holder scoping; cross-holder → 404; leak audit (logs/URLs/errors) (AC-6).
3. API: save/list/recall/delete routes (recall refreshes `last_accessed_at`) + get/update prefs; transactional tests (AC-1, AC-2).
4. TTL sweep for 90-day-expired routes; prefs persist (AC-7).
5. Frontend: save button, saved list + recall + delete, prefs editor, invisible token bootstrap (AC-1, AC-2).
6. Regression: SQLite cache suite (001 AC-3) + full gates green (AC-4, AC-5).

## Risks / Open Questions
- Postgres in dev/CI is new infra — container/service pinned at scaffold; cache tests remain SQLite-only.
- Depends on 001 (routes to save); independent of 004/006/007/008.
