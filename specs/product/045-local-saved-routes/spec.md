# 045 Local Saved Routes — Spec

Status: approved by grilling (2026-11-28); ready for the queue.

## What / Why

Saved routes currently require Postgres. On the free Render deployment there is
no `DATABASE_URL`, so the whole feature is hidden; adding a full SQL service
just to keep a few route snapshots is disproportionate. The walker’s browser is
the natural durable home for their own saved walks, and a small JSON file on the
server is enough for a best-effort backup/transfer cache.

This spec makes **localStorage the primary store** for routes and preferences,
with a JSON file sync cache behind the existing bearer-token identity. It
removes Postgres, Alembic, psycopg and the DB tooling entirely.

## Decisions (grilled, 2026-11-28)

- **Durability:** browser-first. The backend JSON file may reset on a free
  Render deploy/restart; the browser copy is the durable one and re-syncs.
- **Cross-device:** per-browser for v1; a copyable **sync code** (the existing
  bearer token) lets a second browser adopt the holder and merge.
- **Source of truth:** the browser (localStorage) is primary; the server is a
  sync/backup cache.
- **Store scope:** saved routes **and** preferences.
- **Server store:** one JSON file, single uvicorn worker, atomic
  `os.replace`, process lock. `SAVED_ROUTES_FILE` overrides the path.
- **Postgres:** remove fully — psycopg, Alembic, migrations, `app/db.py`,
  DB repositories, `DATABASE_URL`, `db.sh`/Makefile DB targets, DB live checks.
- **Sync API:** full snapshot `GET/PUT /saved-routes/snapshot`; the old CRUD
  endpoints are removed.
- **Conflicts:** per-route and prefs **version counter**; the server stores the
  max. Ties break on `updated_at`, then id. No device-clock trust.
- **Deletes:** a local delete is a pending delete until the next successful
  push; on ack it is purged. A pull deletes a **synced** local route that is
  absent remotely; an unsynced local route is kept and pushed.
- **Sync trigger:** on load and after each change (debounced), with an offline
  queue and replay; a status line and Retry in the Saved dialog.
- **Sync flag:** `SAVED_SYNC=0` disables only the backend path; local Saved
  always works. Default on.
- **Quota:** 300 routes / ~4 MB. Evict the **oldest already-synced** routes and
  toast; if every route is unsynced, refuse the save with a clear message.
  Never silently evict unsynced work.
- **TTL:** 90 days since **last access**; recall refreshes it. The sweep is
  silent and applies to **all** routes (synced or not); it runs on load.
  TTL deletions join the pending-delete queue when sync is on.
- **Sync code:** the existing token, shown with a warning that anyone holding
  it can read/write the anonymous routes. Entering a code adopts that holder,
  pulls the remote snapshot, merges local unsynced routes, and pushes.
- **Export/import:** later; not in this release.
- **Migration:** keep `swarm_saved_routes_token`; new namespaced local keys
  (`cwr:saved:v1`), migrated on first load.

## Contract sketch

Local (`localStorage`):

```json
{
  "version": 1,
  "routes": {
    "<uuid>": {
      "id": "<uuid>",
      "request": {...},
      "response": {...},
      "created_at": "...",
      "updated_at": "...",
      "last_accessed_at": "...",
      "version": 3,
      "synced": false
    }
  },
  "prefs": {"default_preference": "hot", "...": "...", "version": 2, "synced": true},
  "pending_deletes": ["<uuid>"],
  "last_sync_at": "..."
}
```

Server (`SAVED_ROUTES_FILE`, default `data/saved_routes.json`):

```json
{
  "version": 1,
  "holders": {
    "<token_sha256>": {
      "routes": {"<uuid>": {"request": {}, "response": {}, "version": 3,
                             "created_at": "...", "updated_at": "...",
                             "last_accessed_at": "..."}},
      "prefs": {"default_preference": "hot", "version": 2, "updated_at": "..."},
      "revision": 12
    }
  }
}
```

`GET /saved-routes/snapshot` returns the holder’s routes/prefs/revision.
`PUT` accepts `{routes, prefs, deleted_ids}`; the server merges by version
(max), applies deletes, increments `revision`, and returns the canonical
snapshot. Every endpoint keeps the bearer-token scoping; tokens are hashed,
never logged or put in URLs. `/capabilities` reports `saved_routes: true`
(local) and a separate `sync` flag.

## Acceptance Criteria

- [ ] AC-1: **Local store.** Routes and preferences save, list, recall and
  delete entirely in localStorage; a reload preserves them; no backend is
  needed. The existing browser token is kept and the new keys are migrated.
- [ ] AC-2: **Quota and TTL.** The 300-route/4 MB cap evicts the oldest synced
  routes with a visible notice and refuses a save when every route is unsynced;
  the silent 90-day-from-last-access sweep runs on load, applies to all routes,
  and recall refreshes the timer. Unit/e2e tests cover both.
- [ ] AC-3: **JSON sync cache.** A single-worker JSON file store with atomic
  replace + lock backs `GET/PUT /saved-routes/snapshot`; bearer scoping, version
  LWW, pending deletes, delete-stale-absent and purge-after-ack behave as
  specified. The store works with `SAVED_ROUTES_FILE` and survives concurrent
  writes without corruption.
- [ ] AC-4: **Sync lifecycle and code.** Sync runs on load and after a change,
  queues offline mutations, retries, and shows local/synced/offline status. The
  token is shown as a copyable sync code with a warning; entering a code adopts
  the holder, pulls, merges local unsynced routes and pushes. `SAVED_SYNC=0`
  leaves local Saved working with no backend calls.
- [ ] AC-5: **Postgres removal.** psycopg, Alembic, `app/migrations`,
  `app/db.py`, the DB repository layer, `DATABASE_URL`, `db.sh`/Makefile DB
  targets and the DB live lane are gone; no test or run needs Postgres. 005 is
  rewritten to the local/sync contract; `/capabilities` no longer hides Saved
  merely because the database is absent.
- [ ] AC-6: **Verification.** App gates (`pytest`, ruff, mypy, frontend
  check/lint/unit), the e2e suite, the strict acceptance for 001–045 and a live
  file-store sync round-trip pass; docs and the 005 acceptance are updated; no
  operator-written feature code (the queue owns the implementation).

## Non-goals

- Accounts, passwords, sharing beyond the sync code, or automatic cross-device
  sync in the background (the code is manual for v1).
- A persistent Render disk or external database; the JSON file is best-effort.
- Export/import UI in this release.
- Real-time collaboration or conflict prompts.
- Changing the route/comfort payloads or the 005 visual language.

## Risks / accepted trade-offs

- A free Render restart wipes the JSON file; the browser re-populates it on the
  next sync. A second browser that has not synced cannot see a deleted route.
- Tombstones are not kept after ack; delete-stale-absent (synced flag) covers
  the normal case, and an old unsynced copy can still resurrect a route.
- The silent TTL can delete an unsynced route after 90 days (explicitly chosen).
- localStorage eviction can remove old synced routes (with a toast), never
  unsynced ones.
- The token as sync code grants read/write access to the anonymous routes;
  accepted with a visible warning.
