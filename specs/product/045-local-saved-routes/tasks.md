# 045 Local Saved Routes — Tasks

- [ ] T1 (AC-1): **Local routes + prefs store.** Add `frontend/src/lib/savedStore.ts`
  with the versioned `cwr:saved:v1` record (routes, prefs, pending deletes,
  last sync), local `list/save/recall/delete` and `get/updatePrefs`, a
  `last_accessed_at` refresh on recall, and a one-time migration that keeps
  `swarm_saved_routes_token`. Wire the Saved dialog and preference panel to the
  local store first; no backend call is required for save/list/recall/delete/
  prefs. Add Vitest coverage for CRUD, prefs and reload/migration. The route
  snapshot shape (`{request,response}`) and the 041 visual language stay
  unchanged.

- [ ] T2 (AC-2): **Quota and TTL.** Enforce 300 routes / ~4 MB in the local
  store: estimate before writing, evict the oldest `synced` routes with a
  visible toast, and refuse a new save when every route is unsynced. On load,
  silently sweep routes older than 90 days since `last_accessed_at` (recall
  refreshes it); add swept ids to `pending_deletes` when sync is on. Cover
  eviction, refusal, TTL-from-last-access and recall-refresh with Vitest and a
  mobile e2e. Do not evict unsynced routes.

- [ ] T3 (AC-3): **JSON file store + snapshot API.** Add
  `app/saved_store.py`: `SAVED_ROUTES_FILE` (default `data/saved_routes.json`,
  gitignored), atomic temp-file + `os.replace`, `fcntl` lock, holder =
  SHA-256 bearer hash, routes/prefs/revision, version-max LWW with
  `updated_at`/id tie-break, delete application and revision increment; a
  corrupt file is a typed error. Replace the CRUD router with
  `GET/PUT /saved-routes/snapshot` (bearer scoped) and update
  `/capabilities` to `saved_routes: true`, `sync: true|false`, `store: "json"`.
  Add pytest for atomic/locked concurrent writes, merge/tie-break/delete,
  corrupt file, scoping and the endpoints. No Postgres import remains in the
  saved-routes path.

- [ ] T4 (AC-4): **Sync lifecycle, status and code.** Pull on load and push
  after each local change (debounced); apply delete-stale-absent only to
  `synced` routes; keep unsynced local routes; mark acked routes `synced` and
  clear `pending_deletes` after ack. Queue while offline and retry with
  backoff. Add the Saved-dialog status (“Saved locally / Synced / Offline —
  will retry”, last sync, Retry) and the **Sync code** section: show/copy the
  token with a warning, and entering a code adopts that holder, pulls, merges
  local unsynced routes, then pushes. `SAVED_SYNC=0` makes no backend calls
  while local Saved keeps working. Add Vitest and e2e for offline save/reload,
  two-context sync-code merge, and the flag.

- [ ] T5 (AC-5): **Remove Postgres and rewrite 005.** Delete `app/db.py`,
  `app/migrations`, the psycopg/Alembic dependencies and the DB repositories
  (replace with `saved_store`); remove `DATABASE_URL` from `render.yaml`,
  `.env.example`, docs and the Makefile; remove `db.sh` and `swarm-db-*`
  targets; remove the DB live checks from 004/005 `live.toml` and the DB gate.
  Rewrite `specs/product/005-saved-routes` to the local/JSON sync contract and
  its acceptance/tests/e2e so nothing skips for a missing DB. `/capabilities`
  must not hide Saved because a database is absent. No test or run may require
  Postgres.

- [ ] T6 (AC-6): **Verification, docs and live round-trip.** Update app
  docs/README/AGENTS/changelog for local-first saved routes, `SAVED_ROUTES_FILE`
  and `SAVED_SYNC`; run pytest, ruff, mypy, frontend check/lint/unit, the full
  e2e suite, the strict acceptance for 001–045 and a live file-store sync
  round-trip (save → snapshot → restore → delete) on the deployed app. Confirm
  no Postgres process is needed, the 90-day/300-route policies are documented,
  and no operator-written feature code was added (the queue owns this spec).
