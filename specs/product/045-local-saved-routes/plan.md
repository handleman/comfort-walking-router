# 045 Local Saved Routes — Plan

1. **Local store module.** Add `frontend/src/lib/savedStore.ts` (or extend
   `savedRoutes.ts`) with a versioned `cwr:saved:v1` record:
   - routes (`id`, `request`, `response`, `created_at`, `updated_at`,
     `last_accessed_at`, `version`, `synced`), prefs, `pending_deletes`,
     `last_sync_at`;
   - `listRoutes`, `saveRoute`, `recallRoute` (refresh `last_accessed_at`),
     `deleteRoute`, `getPrefs`, `updatePrefs`;
   - a one-time migration from the old token key (kept as
     `swarm_saved_routes_token`) and any legacy local keys;
   - a size estimate and explicit quota errors.
2. **Quota and TTL.** Enforce 300 routes / ~4 MB. On overflow, evict the oldest
   `synced` routes and show a toast; if none are synced, refuse the save with a
   clear message. On load, sweep routes whose `last_accessed_at` is older than
   90 days (silent); add their ids to `pending_deletes` when sync is on.
   Recall refreshes `last_accessed_at`.
3. **JSON file store.** Add `app/saved_store.py` with:
   - `SAVED_ROUTES_FILE` (default `data/saved_routes.json`), `.gitignore`,
     atomic temp-file + `os.replace`, and `fcntl` lock on a sidecar;
   - holder = SHA-256 token hash; routes/prefs/revision;
   - `snapshot(holder)`, `merge(holder, routes, prefs, deleted_ids)` with
     version-max LWW, tie-break `updated_at` then id, delete application,
     revision increment; a corrupt file is a typed error, not a 500 crash.
4. **API.** Replace the CRUD router with:
   - `GET /saved-routes/snapshot` and `PUT /saved-routes/snapshot`
     (`SavedSnapshot` request/response models), same bearer dependency;
   - `/capabilities` reports `saved_routes: true` (local) and `sync: bool`
     (`SAVED_SYNC != 0`), plus `store: "json"`;
   - remove the DB import path and 503 branch; a missing/unwritable file is a
     clear 503 for sync only, never for local.
5. **Frontend sync.** Load the local store first, render Saved immediately, then
   sync in the background:
   - pull the snapshot, apply delete-stale-absent (only `synced` routes),
     merge remote routes/prefs by version, push local unsynced routes and
     `pending_deletes`, mark acked routes `synced`, clear deletes;
   - debounce after each mutation; queue while offline; retry with a backoff;
   - status: “Saved locally”, “Synced”, “Offline — will retry”, last sync and a
     Retry action; `SAVED_SYNC=0` makes no backend calls.
6. **Sync code UI.** In the Saved dialog, add a “Sync code” section with the
   token, copy + warning. Entering a code sets the token, pulls that holder,
   merges local unsynced routes, and pushes. No accounts.
7. **Remove Postgres.** Delete `app/db.py`, `app/migrations`, the Postgres
   repositories (replace with `saved_store`), `DATABASE_URL` from render/env
   docs, `db.sh`/Makefile DB targets and `live.toml` DB checks; rewrite 005’s
   acceptance/tests/e2e to local + JSON. Keep the unrelated route cache as-is.
8. **Tests.**
   - Vitest: local CRUD/prefs, migration, quota evict/refuse, TTL, delete-stale,
     version merge, sync-code adoption.
   - Pytest: JSON atomic write/lock/concurrent merge, LWW/tie-break, delete,
     corrupt file, bearer scoping, snapshot API, capabilities.
   - E2E: save → reload → list → recall → delete with the backend blocked;
     then sync on, save on one context, enter the code in a second context and
     see the route; TTL/quota UI.
   - Strict acceptance 001–045; no Postgres; live file-store sync round-trip.
9. **Docs/rollout.** Update the app docs/AGENTS/README/005 status; add the
   `SAVED_ROUTES_FILE`/`SAVED_SYNC` envs; deploy, run the live sync check, and
   keep 041’s operator exception unchanged.

## Risks

- localStorage is synchronous and quota-bound; every write must estimate size
  before mutating, and a failed save must leave the previous record intact.
- JSON file writes need the lock even with one worker (tests and reloads can
  overlap); atomic replace protects readers.
- The browser clock is not trusted for ordering; versions are per-route, and
  `updated_at` is only a tie-break.
- Delete-stale-absent needs the `synced` flag; a bug there can delete local
  routes. Cover it with explicit tests.
- Removing Postgres touches 004/005 tests and the live lane; do it in one
  coherent task so no test silently skips a missing DB.
