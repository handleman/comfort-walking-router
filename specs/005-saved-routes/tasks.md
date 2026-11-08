# 005 Saved Routes — Tasks

- [ ] T1 (AC-3, AC-5): Add Postgres deps to `requirements.txt` and `app/db.py` (DATABASE_URL config, connection + migration runner) with unit tests in `tests/test_db.py` that skip when `DATABASE_URL` is unset.
- [ ] T2 (AC-3): Add up/down migrations under `app/migrations/` for `holders`, `routes`, `prefs` and migration tests in `tests/test_migrations.py`.
- [ ] T3 (AC-6): Token mint/hash helpers in `app/auth.py` (128-bit opaque, hash stored, never logged) with tests in `tests/test_auth.py`.
- [ ] T4 (AC-1, AC-6): Routes repository in `app/repositories/routes.py` (save/list/recall/delete, holder scoping, wrong holder → 404) with tests in `tests/test_routes_repo.py`.
- [ ] T5 (AC-2): Prefs repository in `app/repositories/prefs.py` (one row per holder, get/update survives restart) with tests in `tests/test_prefs_repo.py`.
- [ ] T6 (AC-1, AC-2, AC-6): Add save/list/recall/delete + prefs API endpoints with bearer dependency in `app/saved_routes.py`, mounted from `app/main.py`, with API tests in `tests/test_saved_routes_api.py`.
- [ ] T7 (AC-7): Add the 90-day TTL sweep in `app/retention.py` (recall refreshes `last_accessed_at`, prefs persist) with tests in `tests/test_retention.py`.
- [ ] T8 (AC-1, AC-2): Add Svelte save/list/recall/delete + prefs editor + invisible token bootstrap in `frontend/src/App.svelte` and `frontend/src/lib/savedRoutes.ts`; keep `npm run check` green.
- [ ] T9 (AC-4, AC-5): Add the SQLite cache regression test in `tests/test_cache_regression.py` and confirm the full app gates stay green.

<!-- Human/infra gate, not queued: provision Postgres + set DATABASE_URL for live repo tests;
     the unit suite skips DB-backed tests when it is unset. -->
