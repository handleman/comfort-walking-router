# 005 Saved Routes — Tasks

- [x] T1 (AC-3, AC-5): Add Postgres deps to `requirements.txt` and `app/db.py` (DATABASE_URL config, connection + migration runner) with unit tests in `tests/test_db.py` that skip when `DATABASE_URL` is unset.
- [x] T2 (AC-3): Add up/down migrations under `app/migrations/` for `holders`, `routes`, `prefs` and migration tests in `tests/test_migrations.py`.
- [x] T3 (AC-6): Token mint/hash helpers in `app/auth.py` (128-bit opaque, hash stored, never logged) with tests in `tests/test_auth.py`.
- [x] T4 (AC-1, AC-6): Routes repository in `app/repositories/routes.py` (save/list/recall/delete, holder scoping, wrong holder → 404) with tests in `tests/test_routes_repo.py`.
- [x] T5 (AC-2): Prefs repository in `app/repositories/prefs.py` (one row per holder, get/update survives restart) with tests in `tests/test_prefs_repo.py`.
- [x] T6 (AC-1, AC-2, AC-6): Add save/list/recall/delete + prefs API endpoints with bearer dependency in `app/saved_routes.py`, mounted from `app/main.py`, with API tests in `tests/test_saved_routes_api.py`.
- [x] T7 (AC-7): Add the 90-day TTL sweep in `app/retention.py` (recall refreshes `last_accessed_at`, prefs persist) with tests in `tests/test_retention.py`.
- [x] T8 (AC-1, AC-2): Add Svelte save/list/recall/delete + prefs editor + invisible token bootstrap in `frontend/src/App.svelte` and `frontend/src/lib/savedRoutes.ts`; keep `npm run check` green.
- [x] T9 (AC-4, AC-5): Add the SQLite cache regression test in `tests/test_cache_regression.py` and confirm the full app gates stay green.

<!-- Human/infra gate, not queued: provision Postgres + set DATABASE_URL for live repo tests;
     the unit suite skips DB-backed tests when it is unset. -->
- [ ] T7 (AC-1): **The client and the API disagree.** The frontend (`frontend/src/lib/savedRoutes.ts`) POSTs `{name, snapshot}` and expects `{id,name,snapshot,…}`, but `app/saved_routes.py` accepts `{request, response}` and `app/repositories/routes.py` returns rows with `request`/`response`. `make accept-live` proves it: `POST /saved-routes → 422`, so save/recall never worked with the DB. Align one contract (simplest: send `{request:{name}, response:snapshot}` and map the list/recall in the client) and add a DB-backed round-trip test (save → list → recall → delete). Verify with `make swarm-db-up`, `make test`, `make accept-live ARGS="--spec 005"`.
